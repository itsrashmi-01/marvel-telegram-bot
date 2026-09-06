// ==========================================
// CORS HEADERS FOR BLOGGER INTEGRATION
// ==========================================
const corsHeaders = {
  "Access-Control-Allow-Origin": "*", // You can restrict this to "https://yourblog.blogspot.com" later
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request, env, ctx) {
    // 1. Handle preflight CORS requests from the browser
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // 2. Extract the movie ID from the URL (e.g., ?id=5)
      const url = new URL(request.url);
      const movieId = url.searchParams.get("id");

      if (!movieId) {
        return new Response(JSON.stringify({ error: "No Movie ID provided" }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      // 3. Prepare the MongoDB Atlas Data API request
      const mongoEndpoint = `${env.MONGO_ENDPOINT}/action/findOne`;
      
      const payload = {
        dataSource: "Cluster0", // Replace with your exact Atlas Cluster Name if different
        database: "marvel_bot", // Your MongoDB database name
        collection: "movies",   // Your MongoDB collection name
        filter: { 
          watch_order: parseInt(movieId) 
        }
      };

      // 4. Fetch the data from MongoDB
      const mongoResponse = await fetch(mongoEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Request-Headers": "*",
          "api-key": env.MONGO_API_KEY
        },
        body: JSON.stringify(payload)
      });

      const data = await mongoResponse.json();

      // 5. Check if the movie exists
      if (!data.document) {
        return new Response(JSON.stringify({ error: "Movie not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json", ...corsHeaders }
        });
      }

      // 6. Return the movie data cleanly to Blogger
      return new Response(JSON.stringify(data.document), {
        status: 200,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });

    } catch (error) {
      return new Response(JSON.stringify({ error: "Internal Server Error", details: error.message }), {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders }
      });
    }
  }
};
