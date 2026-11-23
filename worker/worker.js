const CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json"
};

const GITHUB_PRODUCTS_URLS = [
    "https://raw.githubusercontent.com/itsrashmi-01/marvel-telegram-bot/main/worker/products.json",
    "https://raw.githubusercontent.com/itsrashmi-01/marvel-telegram-bot/master/worker/products.json"
];

function jsonRes(data, status = 200) {
    return new Response(JSON.stringify(data), {
        status,
        headers: CORS_HEADERS
    });
}

function getBackendConfig(env) {
    const baseUrl = (env.RENDER_URL || env.BACKEND_URL || "https://movie-post-bot.onrender.com")
        .trim()
        .replace(/\/+$/, "");
    const secret = (env.SECRET_KEY || env.WORKER_SECRET || "").trim();
    return { baseUrl, secret };
}

async function postToRender(env, path, payload, timeoutMs = 8000) {
    const { baseUrl, secret } = getBackendConfig(env);
    if (!baseUrl) {
        throw new Error("RENDER_URL is missing");
    }

    const headers = {
        "Content-Type": "application/json"
    };
    if (secret) {
        headers["X-Worker-Secret"] = secret;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const resp = await fetch(`${baseUrl}${path}`, {
            method: "POST",
            signal: controller.signal,
            headers,
            body: JSON.stringify(payload)
        });
        clearTimeout(timer);

        const text = await resp.text();
        let data = {};
        try {
            data = text ? JSON.parse(text) : {};
        } catch (_) {
            data = { raw: text };
        }

        if (!resp.ok) {
            return {
                ok: false,
                status: resp.status,
                error: data.error || `Backend returned ${resp.status}`,
                data
            };
        }

        return { ok: true, status: resp.status, data };
    } catch (err) {
        clearTimeout(timer);
        return {
            ok: false,
            status: 502,
            error: err.message || "Failed to reach backend",
            data: {}
        };
    }
}

function normalizeProducts(rawList) {
    if (!Array.isArray(rawList)) return [];
    return rawList.map((item, idx) => ({
        id: String(item.id || `prod-${idx + 1}`),
        title: String(item.title || "Product").trim(),
        price: String(item.price || "").trim(),
        platform: String(item.platform || "Store").trim(),
        category: String(item.category || "General").trim() || "General",
        image: String(item.image || "").trim(),
        url: String(item.url || "#").trim()
    }));
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

async function fetchProductsFromGitHub(env) {
    const urls = [];
    if (env.GITHUB_PRODUCTS_JSON_URL && String(env.GITHUB_PRODUCTS_JSON_URL).trim()) {
        urls.push(String(env.GITHUB_PRODUCTS_JSON_URL).trim());
    }
    urls.push(...GITHUB_PRODUCTS_URLS);

    for (const rawUrl of urls) {
        const sep = rawUrl.includes("?") ? "&" : "?";
        const bustUrl = `${rawUrl}${sep}t=${Math.floor(Date.now() / 60000)}`;

        const resp = await fetch(bustUrl, {
            method: "GET",
            headers: {
                "User-Agent": "Cloudflare-Worker-Jarvis/1.0",
                "Accept": "application/json"
            },
            cf: {
                cacheTtl: 60,
                cacheEverything: true
            }
        });

        if (resp.ok) {
            const parsed = await resp.json();
            if (Array.isArray(parsed)) return parsed;
            if (Array.isArray(parsed?.products)) return parsed.products;
            return [];
        }
    }

    throw new Error("Could not fetch worker/products.json from GitHub");
}

async function handleGetProducts(env) {
    const rawItems = await fetchProductsFromGitHub(env);
    const items = normalizeProducts(rawItems);
    return jsonRes(groupByCategory(items), 200);
}

async function handleGetDownloadLink(env, body) {
    const movieId = body.id ?? body.movie_id ?? body.watch_order;
    if (movieId === undefined || movieId === null || String(movieId).trim() === "") {
        return jsonRes({ error: "Missing movie id" }, 400);
    }

    const result = await postToRender(env, "/api/fetch", {
        id: movieId,
        quality: body.quality || "",
        file_index: body.file_index ?? body.idx ?? null
    });

    if (!result.ok) {
        return jsonRes({ error: result.error }, result.status >= 400 ? result.status : 502);
    }

    const doc = result.data?.document || null;
    if (!doc) {
        return jsonRes({ document: null, download_url: null, files: [] }, 200);
    }

    const files = Array.isArray(doc.files) ? doc.files : [];
    const requestedIndex =
        body.file_index !== undefined && body.file_index !== null
            ? Number(body.file_index)
            : body.idx !== undefined && body.idx !== null
                ? Number(body.idx)
                : -1;

    let selectedFile = null;
    if (!Number.isNaN(requestedIndex) && requestedIndex >= 0 && requestedIndex < files.length) {
        selectedFile = files[requestedIndex];
    } else if (body.quality) {
        const qTarget = String(body.quality).trim().toLowerCase();
        selectedFile =
            files.find((f) => String(f.quality || "").trim().toLowerCase() === qTarget) || null;
    } else if (files.length > 0) {
        selectedFile = files[0];
    }

    const downloadUrl =
        selectedFile?.telegram_link ||
        selectedFile?.url ||
        selectedFile?.link ||
        files.find((f) => f.telegram_link || f.url || f.link)?.telegram_link ||
        null;

    return jsonRes({
        document: doc,
        file: selectedFile,
        download_url: downloadUrl,
        files
    }, 200);
}

export default {
    async fetch(request, env) {
        try {
            if (request.method === "OPTIONS") {
                return new Response(null, { status: 204, headers: CORS_HEADERS });
            }
            if (request.method !== "POST") {
                return jsonRes({ error: "Method not allowed" }, 405);
            }

            const body = await request.json();
            const action = String(body.action || "").trim();

            if (action === "get_products") {
                return await handleGetProducts(env);
            }

            if (action === "get_link" || action === "download" || action === "meta" || action === "fetch_movie") {
                return await handleGetDownloadLink(env, body);
            }

            return jsonRes({ error: "Unsupported action" }, 400);
        } catch (err) {
            return jsonRes({ error: err.message || "Internal error" }, 500);
        }
    }
};
