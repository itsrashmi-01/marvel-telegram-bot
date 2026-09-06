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
      // Added 'type' to the extracted variables
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
        const safeData = {
          title: movieData.title,
          // Poster is completely removed. We now send quality and size directly.
          files: movieData.files ? movieData.files.map(f => ({
              quality: f.quality,
              size: f.size || f.size_str || "Available" // Adjust based on your DB field
          })) : []
        };
        return new Response(JSON.stringify(safeData), { 
            status: 200, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      } 
      
      else if (action === "get_link") {
        if (!movieData.files) {
            return new Response(JSON.stringify({ error: "No files available for this movie." }), { status: 404, headers: corsHeaders });
        }
        
        const file = movieData.files.find(f => f.quality === quality);
        if (!file) {
            return new Response(JSON.stringify({ error: "Requested quality not found." }), { status: 404, headers: corsHeaders });
        }
        
        // Route exactly to the right URL based on the button clicked
        let finalUrl = "";
        if (type === "telegram") {
            finalUrl = file.telegram_link || file.url; // Adjust to your DB's telegram link field
        } else {
            finalUrl = file.mediafire_link || file.url; // Adjust to your DB's direct link field
        }

        return new Response(JSON.stringify({ url: finalUrl }), { 
            status: 200, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      }

      return new Response(JSON.stringify({ error: "Invalid Action" }), { status: 400, headers: corsHeaders });

    } catch (error) {
      return new Response(JSON.stringify({ error: `Server Error: ${error.message}` }), { status: 500, headers: corsHeaders });
    }
  }
};
