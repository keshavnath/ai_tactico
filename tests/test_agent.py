"""Test script for tactical agent end-to-end."""
import os
import sys
import time
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import Neo4jClient
from src.agent import create_agent

# Configuration from env
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:1.7b")


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


def check_ollama(llm_client) -> bool:
    """Verify Ollama service is running and model is available."""
    if llm_client.health_check():
        print(f"[OK] Ollama running with model '{LLM_MODEL}'")
        return True
    else:
        print(f"[FAIL] Ollama not responding OR model '{LLM_MODEL}' not available")
        print(f"       1. Start Ollama: ollama serve")
        print(f"       2. In another terminal, pull model: ollama pull {LLM_MODEL}")
        return False


def main():
    """Run agent test."""
    print("=" * 60)
    print("TACTICAL FOOTBALL AGENT - TEST")
    print("=" * 60)
    print()
    
    # Initialize connections
    print("Initializing...")
    try:
        db = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
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
        agent = create_agent(db, llm_base_url=LLM_BASE_URL, llm_model=LLM_MODEL)
        print("[OK] Agent created")
    except Exception as e:
        print(f"[FAIL] Agent creation failed: {e}")
        db.close()
        return 1
    
    # Check LLM
    print("\n3. Checking Ollama service...")
    if not check_ollama(agent.llm):
        db.close()
        return 1
    
    # Test with sample question
    print("\n4. Running sample analysis...")
    print("-" * 60)
    
    questions = [
        "Who scored in the match?",
        "How aggressive was the defense?",
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
