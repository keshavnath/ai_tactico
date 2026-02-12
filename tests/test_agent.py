"""Test script for tactical agent end-to-end."""
import sys
import time
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.db import Neo4jClient
from src.agent import create_agent


def check_neo4j(client: Neo4jClient) -> bool:
    """Verify Neo4j connection."""
    try:
        result = client.query("MATCH (n) RETURN COUNT(*) as count LIMIT 1")
        count = result[0]["count"]
        print(f"[OK] Neo4j connected ({count} total nodes)")
        return True
    except Exception as e:
        print(f"[FAIL] Neo4j connection failed: {e}")
        return False


def check_llm_service(llm_client) -> bool:
    """Verify LLM service is running and responding."""
    if llm_client.health_check():
        print(f"[OK] LLM service responding with model '{config.LLM_MODEL}'")
        return True
    else:
        print(f"[FAIL] LLM service not responding (model: {config.LLM_MODEL})")
        print(f"       Verify:")
        print(f"       - Service is running at {config.LLM_BASE_URL}")
        print(f"       - Model '{config.LLM_MODEL}' is available")
        print(f"       - API key is correct (if required)")
        return False


def main():
    """Run agent test."""
    print("=" * 60)
    print("TACTICAL FOOTBALL AGENT - TEST")
    print("=" * 60)
    print()
    
    # Display configuration
    config.display()
    print()
    
    # Initialize connections
    print("Initializing...")
    try:
        db = Neo4jClient(config.NEO4J_URI, config.NEO4J_USER, config.NEO4J_PASSWORD)
    except Exception as e:
        print(f"[FAIL] Failed to create Neo4j client: {e}")
        return 1
    
    # Check database
    print("\n1. Checking Neo4j database...")
    if not check_neo4j(db):
        db.close()
        return 1
    
    # Create agent
    print("\n2. Creating agent...")
    try:
        agent = create_agent(
            db,
            llm_base_url=config.LLM_BASE_URL,
            llm_model=config.LLM_MODEL,
            llm_api_key=config.LLM_API_KEY,
            max_iterations=config.AGENT_MAX_ITERATIONS,
        )
        print("[OK] Agent created")
    except Exception as e:
        print(f"[FAIL] Agent creation failed: {e}")
        db.close()
        return 1
    
    # Check LLM service
    print("\n3. Checking LLM service...")
    if not check_llm_service(agent.llm):
        db.close()
        return 1
    
    # Test with sample questions - now with time-bounded and specific queries
    print("\n4. Running sample analysis with event-centric and time-bounded queries...")
    print("-" * 60)
    
    questions = [
        "Explain the buildup to the first goal",
        "Who pressed the most in the first 20 minutes?",
        "Show me Benzema's shots in the match",
        "Which players passed to each other the most in the second half?",
        "How many tackles happened minute 30-45?",
    ]
    
    test_passed = True
    
    for question in questions:
        print(f"\nQ: {question}")
        print("A: ", end="", flush=True)
        
        try:
            start = time.time()
            answer = agent.analyze(question)
            elapsed = time.time() - start
            
            # Truncate long answers for display
            display_answer = answer[:200] + "..." if len(answer) > 200 else answer
            print(display_answer)
            print(f"   ({elapsed:.1f}s)")
            
        except Exception as e:
            print(f"ERROR: {e}")
            test_passed = False
    
    db.close()
    
    print("\n" + "=" * 60)
    if test_passed:
        print("[OK] Test completed successfully")
    else:
        print("[FAIL] Test had errors")
    print("=" * 60)
    return 0 if test_passed else 1


if __name__ == "__main__":
    sys.exit(main())
