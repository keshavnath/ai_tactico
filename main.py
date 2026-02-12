"""Flask web app for AI Tactico - minimal frontend for agent interaction."""
from flask import Flask, render_template, request, jsonify
from src.config import config
from src.agent import create_agent
from src.db import Neo4jClient


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__, 
        template_folder="src/frontend/templates",
        static_folder="src/frontend/static"
    )
    
    # Validate configuration
    if not config.validate():
        raise RuntimeError("Configuration validation failed. Check your .env file and environment variables.")
    
    # Initialize database
    db = Neo4jClient(
        uri=config.NEO4J_URI,
        user=config.NEO4J_USER,
        password=config.NEO4J_PASSWORD,
    )
    
    # Initialize agent with configuration
    agent = create_agent(
        db,
        llm_base_url=config.LLM_BASE_URL,
        llm_model=config.LLM_MODEL,
        llm_api_key=config.LLM_API_KEY,
        max_iterations=config.AGENT_MAX_ITERATIONS,
    )
    
    # Load match info
    def get_match_info():
        """Get basic match information for display."""
        try:
            result = db.query("""
            MATCH (m:Match)<-[:IN_MATCH]-(e:Event)
            MATCH (m)<-[:IN_MATCH]-(team:Team)
            RETURN 
                m.id as match_id,
                m.match_date as match_date,
                COLLECT(DISTINCT team.name) as teams,
                COUNT(DISTINCT e) as event_count
            LIMIT 1
            """)
            
            if result:
                return result[0]
            return None
        except Exception as e:
            print(f"Error loading match info: {e}")
            return None
    
    match_info = get_match_info()
    
    @app.route("/")
    def index():
        """Render the home page."""
        return render_template("index.html", match=match_info)
    
    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        """Endpoint for agent analysis.
        
        Expects JSON: {"question": "..."}
        Returns JSON: {"answer": "..."}
        """
        data = request.get_json()
        question = data.get("question", "").strip()
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        try:
            # Run agent analysis
            answer = agent.analyze(question)
            
            return jsonify({
                "question": question,
                "answer": answer,
                "success": True
            })
        except Exception as e:
            return jsonify({
                "error": str(e),
                "success": False
            }), 500
    
    @app.route("/api/match")
    def get_match():
        """Get match information as JSON."""
        return jsonify(match_info or {})
    
    return app


def main():
    """Run the Flask development server."""
    print()
    
    app = create_app()
    app.run(debug=config.DEBUG, host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
