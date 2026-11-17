// Helper: Scrapes MediaFire page for the raw direct-download URL and exact file size
async function resolveMediaFire(mfUrl) {
  if (!mfUrl || !mfUrl.includes("mediafire.com")) {
    return { directUrl: mfUrl, size: "" };
  }
  try {
    const res = await fetch(mfUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
      }
    });
    const html = await res.text();

    // 1. Extract raw direct download link (https://downloadXXXX.mediafire.com/...)
    const linkMatch =
      html.match(/href="(https?:\/\/download\d+\.mediafire\.com\/[^"]+)"/i) ||
      html.match(/id="downloadButton"[^>]*href="([^"]+)"/i);

    // 2. Extract file size from button text e.g. "Download (1.24 GB)"
    const sizeMatch =
      html.match(/Download\s*\(([\d.]+\s*[KMGT]?B)\)/i) ||
      html.match(/<li>File size:\s*<span>([\d.]+\s*[KMGT]?B)<\/span>/i);

    return {
      directUrl: linkMatch ? linkMatch[1] : mfUrl,
      size: sizeMatch ? sizeMatch[1] : ""
    };
  } catch (e) {
    return { directUrl: mfUrl, size: "" };
  }
}

// Helper: Formats bytes if your DB stores size as a raw number
function formatSize(val) {
  if (!val) return "";
  if (typeof val === "number" || /^\d+$/.test(String(val))) {
    const bytes = Number(val);
    if (bytes <= 0) return "";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }
  return String(val);
}

// Helper: Extracts 480p / 720p / 1080p / 4K from filename or title if missing
function normalizeQuality(q, fallbackStr = "") {
  if (q && q.trim() !== "") return q.trim();
  const match = fallbackStr.match(/\b(480p|720p|1080p|1440p|2160p|4K)\b/i);
  return match ? match[1] : "HD";
}

export default {
  async fetch(request, env, ctx) {
    // 1. STRICT ORIGIN CHECKING
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
    
    if (request.method !== "POST") return new Response(JSON.stringify({ error: "Method Not Allowed" }), { 
        status: 405, 
        headers: { "Content-Type": "application/json", ...corsHeaders } 
    });

    try {
      const body = await request.json();
      const { id, t, hash, action, quality, type } = body;

      if (!id || !t || !hash || !action) {
         return new Response(JSON.stringify({ error: "Missing required security parameters" }), { 
             status: 400, 
             headers: { "Content-Type": "application/json", ...corsHeaders } 
         });
      }

      // 2. VERIFY 1-HOUR EXPIRATION
      const currentTime = Math.floor(Date.now() / 1000);
      if (currentTime > parseInt(t)) {
        return new Response(JSON.stringify({ error: "Link Expired. Please request a new link from the bot." }), { 
            status: 401, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      }

      // 3. VERIFY CRYPTOGRAPHIC SIGNATURE
      const encoder = new TextEncoder();
      const data = encoder.encode(`${id}${t}${env.SECRET_KEY}`);
      const hashBuffer = await crypto.subtle.digest('SHA-256', data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const expectedHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

      if (hash !== expectedHash) {
        return new Response(JSON.stringify({ error: "Invalid Security Token. Access Denied." }), { 
            status: 401, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      }

      // 4. FETCH DATA FROM YOUR RENDER SERVER
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

      // 5. ROUTE ACTIONS SECURELY
      if (action === "meta") {
        const rawFiles = movieData.files || [];
        
        // Resolve sizes & qualities (auto-scrapes MediaFire if size is missing in DB)
        const filesWithMeta = await Promise.all(rawFiles.map(async (f) => {
          const q = normalizeQuality(f.quality, f.file_name || f.title || f.mediafire_link || "");
          let s = formatSize(f.size || f.file_size || f.size_str || f.fileSize || "");
          
          const mfLink = f.mediafire_link || f.url || "";
          if ((!s || s.toLowerCase() === "available" || s === "Unknown Size") && mfLink.includes("mediafire.com")) {
            const resolved = await resolveMediaFire(mfLink);
            if (resolved.size) s = resolved.size;
          }
          return { quality: q, size: s };
        }));

        return new Response(JSON.stringify({
          title: movieData.title,
          files: filesWithMeta
        }), { 
            status: 200, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      } 
      
      else if (action === "get_link") {
        if (!movieData.files) {
            return new Response(JSON.stringify({ error: "No files available for this movie." }), { status: 404, headers: corsHeaders });
        }
        
        const file = movieData.files.find(f => normalizeQuality(f.quality, f.file_name || f.title || "") === quality) 
                  || movieData.files.find(f => f.quality === quality);

        if (!file) {
            return new Response(JSON.stringify({ error: "Requested quality not found." }), { status: 404, headers: corsHeaders });
        }
        
        if (type === "telegram") {
            const tgUrl = file.telegram_link || file.url;
            if (!tgUrl) return new Response(JSON.stringify({ error: "Telegram link is missing." }), { status: 404, headers: corsHeaders });
            return new Response(JSON.stringify({ url: tgUrl, direct: false }), { 
                status: 200, 
                headers: { "Content-Type": "application/json", ...corsHeaders } 
            });
        } else {
            const rawLink = file.mediafire_link || file.url;
            if (!rawLink) return new Response(JSON.stringify({ error: "Download link is missing." }), { status: 404, headers: corsHeaders });
            
            // Extract the direct download binary URL from MediaFire
            const resolved = await resolveMediaFire(rawLink);
            return new Response(JSON.stringify({ 
                url: resolved.directUrl, 
                size: resolved.size,
                direct: true 
            }), { 
                status: 200, 
                headers: { "Content-Type": "application/json", ...corsHeaders } 
            });
        }
      }

      return new Response(JSON.stringify({ error: "Invalid Action" }), { status: 400, headers: corsHeaders });

    } catch (error) {
      return new Response(JSON.stringify({ error: `Server Error: ${error.message}` }), { status: 500, headers: corsHeaders });
    }
  }
};
