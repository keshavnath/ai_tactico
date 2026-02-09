"""Agent interaction entry point."""
import os
from src.db import Neo4jClient
from src.agent import create_agent

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:1.7b")


def main():
    """Interactive agent session."""
    
    # Initialize
    db = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    agent = create_agent(db, llm_base_url=LLM_BASE_URL, llm_model=LLM_MODEL)
    
    # Verify connection
    if not agent.llm.health_check():
        print("Warning: Could not reach Ollama at {LLM_BASE_URL}")
        print(f"Ensure Ollama is running with: ollama serve")
        print(f"And pull the model: ollama pull {LLM_MODEL}")
        return
    
    # Get match ID
    match_id = "match_18245"
    
    print(f"Tactical Analysis Agent")
    print(f"Match: {match_id}")
    print(f"Connected to Neo4j at {NEO4J_URI}")
    print(f"LLM: {LLM_MODEL} at {LLM_BASE_URL}")
    print()
    
    # Interactive loop
    while True:
        question = input("Ask about the match (or 'exit' to quit):\n> ").strip()
        
        if question.lower() == "exit":
            break
        
        if not question:
            continue
        
        print("\nAnalyzing...\n")
        
        try:
            answer = agent.analyze(question, match_id)
            print("Analysis:")
            print(answer)
            print()
        
        except Exception as e:
            print(f"Error: {e}\n")
    
    db.close()
    print("Goodbye!")


if __name__ == "__main__":
    main()
