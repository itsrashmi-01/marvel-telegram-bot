const CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json"
};

const FALLBACK_IMAGE = "https://ik.imagekit.io/itsrashmi/Marvel%20Sticker/Avengers.webp";

function parseProductsModuleSource(jsSource) {
    const match = jsSource.match(/(?:export\s+)?(?:const|let|var)\s+PRODUCTS\s*=\s*(\[[\s\S]*?\]);/);
    if (!match) {
        throw new Error("Could not find PRODUCTS array in products.js");
    }
    const list = new Function(`return (${match[1]});`)();
    if (!Array.isArray(list)) {
        throw new Error("PRODUCTS is not an array");
    }
    return list;
}

function decodeHtmlEntities(str) {
    return str
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">");
}

function extractMetaFromHtml(html, baseUrl) {
    const getMeta = (pattern) => {
        const m = html.match(pattern);
        return m ? decodeHtmlEntities(m[1].trim()) : "";
    };

    const ogImage =
        getMeta(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)["']/i) ||
        getMeta(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:image["']/i) ||
        getMeta(/<meta[^>]+name=["']twitter:image["'][^>]+content=["']([^"']+)["']/i) ||
        getMeta(/<meta[^>]+content=["']([^"']+)["'][^>]+name=["']twitter:image["']/i);

    const ogTitle =
        getMeta(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)["']/i) ||
        getMeta(/<meta[^>]+content=["']([^"']+)["'][^>]+property=["']og:title["']/i);

    const titleTagMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const rawTitle = ogTitle || (titleTagMatch ? decodeHtmlEntities(titleTagMatch[1].trim()) : "");

    let resolvedImage = FALLBACK_IMAGE;
    if (ogImage) {
        try {
            resolvedImage = new URL(ogImage, baseUrl).toString();
        } catch (_) {
            resolvedImage = FALLBACK_IMAGE;
        }
    }

    return {
        title: rawTitle || "Marvel Deal",
        image: resolvedImage
    };
}

async function fetchProductMetadata(productUrl) {
    if (!productUrl) {
        return { title: "Marvel Deal", image: FALLBACK_IMAGE };
    }
    try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 4500);
        const resp = await fetch(productUrl, {
            signal: controller.signal,
            headers: {
                "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
                "Accept": "text/html,application/xhtml+xml"
            },
            redirect: "follow"
        });
        clearTimeout(timer);
        if (!resp.ok) {
            return { title: "Marvel Deal", image: FALLBACK_IMAGE };
        }
        const html = await resp.text();
        return extractMetaFromHtml(html, resp.url || productUrl);
    } catch (_) {
        return { title: "Marvel Deal", image: FALLBACK_IMAGE };
    }
}

async function convertWithEarnKaro(env, dealUrl) {
    if (!env.EARNKARO_TOKEN || !dealUrl) return dealUrl || "#";
    try {
        const res = await fetch("https://ekaro-api.affiliaters.in/api/converter/public", {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${env.EARNKARO_TOKEN}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ deal: dealUrl })
        });
        const data = await res.json();
        return (res.ok && data && data.data) ? data.data : dealUrl;
    } catch (_) {
        return dealUrl;
    }
}

function groupByCategory(items) {
    const map = new Map();
    for (const item of items) {
        const cat = (item.category && String(item.category).trim()) || "General";
        if (!map.has(cat)) map.set(cat, []);
        map.get(cat).push(item);
    }
    return {
        categoryList: Array.from(map.keys()),
        categories: Array.from(map.entries()).map(([name, list]) => ({
            name,
            count: list.length,
            items: list
        })),
        products: items
    };
}

async function handleGetProducts(env, ctx) {
    const rawGithubUrl = env.GITHUB_PRODUCTS_RAW_URL;
    if (!rawGithubUrl) {
        return new Response(JSON.stringify({ error: "GITHUB_PRODUCTS_RAW_URL missing" }), {
            status: 500,
            headers: CORS_HEADERS
        });
    }

    const cache = caches.default;
    const cacheKey = new Request(`https://cache.local/ek-products-v4?u=${encodeURIComponent(rawGithubUrl)}`);
    const cached = await cache.match(cacheKey);
    if (cached) {
        return new Response(await cached.text(), { status: 200, headers: CORS_HEADERS });
    }

    const ghResp = await fetch(rawGithubUrl, {
        headers: { "User-Agent": "JARVIS-Worker" },
        cf: { cacheTtl: 180, cacheEverything: true }
    });
    if (!ghResp.ok) {
        return new Response(JSON.stringify({ error: "Failed to load products.js" }), {
            status: 502,
            headers: CORS_HEADERS
        });
    }

    const rawProducts = parseProductsModuleSource(await ghResp.text());

    const enriched = await Promise.all(
        rawProducts.map(async (entry, idx) => {
            const sourceLink = (entry.link || entry.rawUrl || entry.url || "").trim();
            const [meta, profitUrl] = await Promise.all([
                fetchProductMetadata(sourceLink),
                entry.url ? Promise.resolve(entry.url.trim()) : convertWithEarnKaro(env, sourceLink)
            ]);

            return {
                id: entry.id || `p-${idx + 1}`,
                title: entry.title || meta.title,
                image: entry.image || meta.image || FALLBACK_IMAGE,
                category: (entry.category && String(entry.category).trim()) || "General",
                platform: entry.platform || "Store",
                url: profitUrl || sourceLink || "#"
            };
        })
    );

    const payload = JSON.stringify(groupByCategory(enriched));
    const cacheResp = new Response(payload, {
        status: 200,
        headers: { ...CORS_HEADERS, "Cache-Control": "public, max-age=180" }
    });
    if (ctx && ctx.waitUntil) {
        ctx.waitUntil(cache.put(cacheKey, cacheResp.clone()));
    }

    return new Response(payload, { status: 200, headers: CORS_HEADERS });
}

export default {
    async fetch(request, env, ctx) {
        if (request.method === "OPTIONS") {
            return new Response(null, { status: 204, headers: CORS_HEADERS });
        }
        if (request.method !== "POST") {
            return new Response(JSON.stringify({ error: "Method not allowed" }), {
                status: 405,
                headers: CORS_HEADERS
            });
        }

        let body = {};
        try {
            body = await request.json();
        } catch (_) {
            return new Response(JSON.stringify({ error: "Invalid JSON" }), {
                status: 400,
                headers: CORS_HEADERS
            });
        }

        if (body.action === "get_products") {
            return handleGetProducts(env, ctx);
        }

        // Keep your existing `meta` / `get_link` handlers here
        return new Response(JSON.stringify({ error: "Unsupported action" }), {
            status: 400,
            headers: CORS_HEADERS
        });
    }
};
