export default {
  async fetch(request, env, ctx) {
    // 1. STRICT ORIGIN CHECKING (Blocks all requests not from your website)
    const origin = request.headers.get("Origin") || request.headers.get("Referer") || "";
    const allowedDomain = env.ALLOWED_DOMAIN || ""; // e.g., "musicjjjdjdj.blogspot.com"
    
    // Only enforce origin check if ALLOWED_DOMAIN is set in Cloudflare variables
    if (allowedDomain && !origin.includes(allowedDomain)) {
      return new Response(JSON.stringify({ error: "Forbidden: Unauthorized Origin" }), { 
        status: 403,
        headers: { "Content-Type": "application/json" }
      });
    }

    // Dynamic CORS to match the verified origin
    const corsHeaders = {
      "Access-Control-Allow-Origin": origin || "*",
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    // Handle preflight requests
    if (request.method === "OPTIONS") return new Response(null, { headers: corsHeaders });
    
    // Only accept POST requests for security
    if (request.method !== "POST") return new Response(JSON.stringify({ error: "Method Not Allowed" }), { 
        status: 405, 
        headers: { "Content-Type": "application/json", ...corsHeaders } 
    });

    try {
      const body = await request.json();
      const { id, t, hash, action, quality } = body;

      if (!id || !t || !hash || !action) {
         return new Response(JSON.stringify({ error: "Missing required security parameters" }), { 
             status: 400, 
             headers: { "Content-Type": "application/json", ...corsHeaders } 
         });
      }

      // 2. VERIFY 1-HOUR EXPIRATION (Timestamp 't' from Telegram)
      const currentTime = Math.floor(Date.now() / 1000);
      if (currentTime > parseInt(t)) {
        return new Response(JSON.stringify({ error: "Link Expired. Please request a new link from the bot." }), { 
            status: 401, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      }

      // 3. VERIFY CRYPTOGRAPHIC SIGNATURE
      const encoder = new TextEncoder();
      // This hashes exactly what the Python bot hashed
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

      // 4. FETCH DATA FROM MONGODB ATLAS
      const mongoPayload = {
        dataSource: "Cluster0", // Replace if your cluster name is different
        database: "marvel_bot", 
        collection: "movies",   
        filter: { watch_order: parseInt(id) }
      };

      const mongoResponse = await fetch(`${env.MONGO_ENDPOINT}/action/findOne`, {
        method: "POST",
        headers: { 
            "Content-Type": "application/json", 
            "api-key": env.MONGO_API_KEY 
        },
        body: JSON.stringify(mongoPayload)
      });

      const dbData = await mongoResponse.json();
      if (!dbData.document) {
        return new Response(JSON.stringify({ error: "Movie not found in database." }), { 
            status: 404, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      }

      const movieData = dbData.document;

      // 5. ROUTE ACTIONS SECURELY
      if (action === "meta") {
        // Send ONLY safe UI data to the frontend, stripping all actual download links
        const safeData = {
          title: movieData.title,
          poster: movieData.images?.poster_url || "",
          qualities: movieData.files ? movieData.files.map(f => f.quality) : []
        };
        return new Response(JSON.stringify(safeData), { 
            status: 200, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      } 
      
      else if (action === "get_link") {
        // Return the requested file link ONLY when explicitly asked via click
        if (!movieData.files) {
            return new Response(JSON.stringify({ error: "No files available for this movie." }), { 
                status: 404, 
                headers: { "Content-Type": "application/json", ...corsHeaders } 
            });
        }
        
        // Find the specific file matching the requested quality
        const file = movieData.files.find(f => f.quality === quality);
        if (!file) {
            return new Response(JSON.stringify({ error: "Requested quality not found." }), { 
                status: 404, 
                headers: { "Content-Type": "application/json", ...corsHeaders } 
            });
        }
        
        // Send back the raw link
        return new Response(JSON.stringify({ url: file.mediafire_link || file.url }), { 
            status: 200, 
            headers: { "Content-Type": "application/json", ...corsHeaders } 
        });
      }

      return new Response(JSON.stringify({ error: "Invalid Action" }), { 
          status: 400, 
          headers: { "Content-Type": "application/json", ...corsHeaders } 
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: "Server Error", details: error.message }), { 
          status: 500, 
          headers: { "Content-Type": "application/json", ...corsHeaders } 
      });
    }
  }
};
