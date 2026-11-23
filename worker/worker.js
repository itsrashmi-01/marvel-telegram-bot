const RAW_PRODUCTS_URL =
  "https://raw.githubusercontent.com/itsrashmi-01/marvel-telegram-bot/main/worker/products.json";

function formatDbSize(val) {
  if (val === undefined || val === null || val === "") return "";
  if (typeof val === "number" || /^\d+$/.test(String(val).trim())) {
    const bytes = Number(val);
    if (bytes <= 0) return "";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }
  const str = String(val).trim();
  if (str.toLowerCase() === "available" || str.toLowerCase() === "unknown size") return "";
  return str;
}

function formatDbQuality(q, fallback = "HD") {
  if (!q) return fallback;
  const str = String(q).trim();
  if (/^\d{3,4}$/.test(str)) return `${str}p`;
  return str;
}

function parseFiles(movieData) {
  const order = movieData.watch_order || movieData.id || "";

  if (Array.isArray(movieData.files) && movieData.files.length > 0) {
    return movieData.files
      .map((f, idx) => {
        const mfLink = String(f.mediafire_link || f.direct_link || f.url || f.link || "").trim();
        const tgLink = String(f.telegram_link || f.tg_link || f.bot_link || "").trim();
        const hasTgFile = Boolean(f.file_id || f.msg_id);
        const hasDirect = Boolean(mfLink);
        const hasTelegram = Boolean(tgLink || hasTgFile);

        return {
          index: idx,
          quality: formatDbQuality(f.quality || f.res || f.resolution || f.label, `File ${idx + 1}`),
          size: formatDbSize(f.size ?? f.file_size ?? f.size_str ?? f.fileSize ?? f.filesize ?? ""),
          mediafire_link: mfLink,
          telegram_link: tgLink,
          has_direct: hasDirect,
          has_telegram: hasTelegram,
          order: order
        };
      })
      .filter(item => item.has_direct || item.has_telegram);
  }

  const qualityKeys = ["480p", "720p", "1080p", "1440p", "2160p", "4K"];
  const extracted = [];
  qualityKeys.forEach((qKey, idx) => {
    const entry = movieData[qKey] || movieData[qKey.toLowerCase()];
    if (!entry) return;

    let mfLink = "";
    let tgLink = "";
    let rawSize = "";
    let hasTgFile = false;

    if (typeof entry === "object") {
      mfLink = String(entry.mediafire_link || entry.direct_link || entry.url || "").trim();
      tgLink = String(entry.telegram_link || entry.tg_link || "").trim();
      rawSize = entry.size || entry.file_size || movieData[`size_${qKey}`] || "";
      hasTgFile = Boolean(entry.file_id || entry.msg_id);
    } else if (typeof entry === "string") {
      mfLink = entry.trim();
      tgLink = String(movieData[`tg_${qKey}`] || "").trim();
      rawSize = movieData[`size_${qKey}`] || movieData.size || "";
      hasTgFile = Boolean(tgLink);
    }

    const hasDirect = Boolean(mfLink);
    const hasTelegram = Boolean(tgLink || hasTgFile);

    if (hasDirect || hasTelegram) {
      extracted.push({
        index: idx,
        quality: qKey,
        size: formatDbSize(rawSize),
        mediafire_link: mfLink,
        telegram_link: tgLink,
        has_direct: hasDirect,
        has_telegram: hasTelegram,
        order: order
      });
    }
  });

  return extracted;
}

async function resolveMediaFireDirectUrl(rawUrl) {
  if (!rawUrl || !rawUrl.includes("mediafire.com")) {
    return rawUrl;
  }
  try {
    const res = await fetch(rawUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    });
    const html = await res.text();
    const match =
      html.match(/href="(https?:\/\/download\d+\.mediafire\.com\/[^"]+)"/i) ||
      html.match(/id="downloadButton"[^>]*href="([^"]+)"/i);
    return match ? match[1] : rawUrl;
  } catch (err) {
    return rawUrl;
  }
}

function groupByCategory(items) {
  const map = new Map();
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const cat = (item.category && String(item.category).trim()) || "General";
    if (!map.has(cat)) map.set(cat, []);
    map.get(cat).push({
      id: String(item.id || ""),
      title: String(item.title || "Product").trim(),
      price: String(item.price || "").trim(),
      platform: String(item.platform || "Store").trim(),
      category: cat,
      image: String(item.image || "").trim(),
      url: String(item.url || "#").trim()
    });
  }

  const categories = Array.from(map.entries()).map(([name, list]) => ({
    name,
    count: list.length,
    items: list
  }));

  return {
    categoryList: Array.from(map.keys()),
    categories,
    products: categories.flatMap((c) => c.items)
  };
}

async function handleGetProducts(env, corsHeaders) {
  const sourceUrl = (env.GITHUB_PRODUCTS_URL || RAW_PRODUCTS_URL).trim();
  const resp = await fetch(sourceUrl, {
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

  if (!resp.ok) {
    return new Response(JSON.stringify({ error: `GitHub fetch failed (${resp.status})` }), {
      status: 502,
      headers: { "Content-Type": "application/json", ...corsHeaders }
    });
  }

  const rawData = await resp.json();
  const items = Array.isArray(rawData)
    ? rawData
    : (Array.isArray(rawData?.products) ? rawData.products : []);

  return new Response(JSON.stringify(groupByCategory(items)), {
    status: 200,
    headers: { "Content-Type": "application/json", ...corsHeaders }
  });
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || request.headers.get("Referer") || "";
    const allowedDomain = env.ALLOWED_DOMAIN || "";

    if (allowedDomain && !origin.includes(allowedDomain)) {
      return new Response(JSON.stringify({ error: "Forbidden: Unauthorized Origin" }), {
        status: 403,
        headers: { "Content-Type": "application/json" }
      });
    }

    const corsHeaders = {
      "Access-Control-Allow-Origin": origin || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method Not Allowed" }), {
        status: 405,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }

    try {
      const body = await request.json();
      const { id, t, hash, action, quality, type } = body;

      if (String(action || "").trim() === "get_products") {
        return await handleGetProducts(env, corsHeaders);
      }

      if (!id || !t || !hash || !action) {
        return new Response(JSON.stringify({ error: "Missing required security parameters" }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const currentTime = Math.floor(Date.now() / 1000);
      if (currentTime > parseInt(t, 10)) {
        return new Response(JSON.stringify({ error: "Link Expired. Please request a new link from the bot." }), {
          status: 401,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const encoder = new TextEncoder();
      const data = encoder.encode(`${id}${t}${env.SECRET_KEY}`);
      const hashBuffer = await crypto.subtle.digest("SHA-256", data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const expectedHash = hashArray.map(b => b.toString(16).padStart(2, "0")).join("");

      if (hash !== expectedHash) {
        return new Response(JSON.stringify({ error: "Invalid Security Token. Access Denied." }), {
          status: 401,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const renderBaseUrl = (env.RENDER_URL || "").replace(/\/+$/, "");
      const renderResponse = await fetch(`${renderBaseUrl}/api/fetch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Worker-Secret": env.SECRET_KEY || ""
        },
        body: JSON.stringify({ id: id })
      });

      if (!renderResponse.ok) {
        const errorText = await renderResponse.text();
        return new Response(JSON.stringify({ error: `Backend Error: ${renderResponse.status} - ${errorText}` }), {
          status: renderResponse.status,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const dbData = await renderResponse.json();
      if (!dbData.document) {
        return new Response(JSON.stringify({ error: "Movie not found in database." }), {
          status: 404,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      const movieData = dbData.document;
      const parsedFiles = parseFiles(movieData);

      if (action === "meta") {
        const releaseYear = movieData.release_year || movieData.year || "";
        const audioLang = (movieData.audio && movieData.audio !== "Pending...") ? movieData.audio : (movieData.language || "");

        const safeData = {
          title: movieData.title || movieData.name || "Movie Download",
          year: releaseYear !== "N/A" ? releaseYear : "",
          release_year: releaseYear !== "N/A" ? releaseYear : "",
          language: audioLang,
          release: movieData.release || "",
          files: parsedFiles.map(f => ({
            quality: f.quality,
            size: f.size,
            has_direct: f.has_direct,
            has_telegram: f.has_telegram
          }))
        };
        return new Response(JSON.stringify(safeData), {
          status: 200,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      else if (action === "get_link") {
        if (!parsedFiles.length) {
          return new Response(JSON.stringify({ error: "No files available for this movie." }), {
            status: 404,
            headers: { "Content-Type": "application/json", ...corsHeaders }
          });
        }

        const targetQuality = String(quality || "").trim().toLowerCase();
        const file = parsedFiles.find(f => f.quality.toLowerCase() === targetQuality);
        if (!file) {
          return new Response(JSON.stringify({ error: "Requested quality not found." }), {
            status: 404,
            headers: { "Content-Type": "application/json", ...corsHeaders }
          });
        }

        if (type === "telegram") {
          if (!file.has_telegram || !file.telegram_link) {
            return new Response(JSON.stringify({ error: "Telegram file is not available for this quality." }), {
              status: 404,
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }
          return new Response(JSON.stringify({ url: file.telegram_link }), {
            status: 200,
            headers: { "Content-Type": "application/json", ...corsHeaders }
          });
        } else {
          if (!file.has_direct || !file.mediafire_link) {
            return new Response(JSON.stringify({ error: "Direct download link is not available for this quality." }), {
              status: 404,
              headers: { "Content-Type": "application/json", ...corsHeaders }
            });
          }

          const directBinaryUrl = await resolveMediaFireDirectUrl(file.mediafire_link);
          return new Response(JSON.stringify({ url: directBinaryUrl, download_url: directBinaryUrl }), {
            status: 200,
            headers: { "Content-Type": "application/json", ...corsHeaders }
          });
        }
      }

      return new Response(JSON.stringify({ error: "Invalid Action" }), {
        status: 400,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: `Server Error: ${error.message}` }), {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }
  }
};
