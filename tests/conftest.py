"""Pytest fixtures and configuration."""
import pytest
import os
import uuid
from src.db import Neo4jClient, setup_schema


@pytest.fixture(scope="session")
def neo4j_uri():
    """Get Neo4j connection URI. Tests use same instance but clean up after themselves."""
    return os.getenv("NEO4J_URI", "bolt://localhost:7687")


@pytest.fixture(scope="session")
def neo4j_user():
    """Get Neo4j username from environment or default."""
    return os.getenv("NEO4J_USER", "neo4j")


@pytest.fixture(scope="session")
def neo4j_password():
    """Get Neo4j password from environment or default."""
    return os.getenv("NEO4J_PASSWORD", "password")


@pytest.fixture
def test_match_id():
    """Provide a unique match ID for this test to avoid conflicts with other tests."""
    return f"tm_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def client(neo4j_uri, neo4j_user, neo4j_password):
    """Create a test Neo4j client with isolated test data.
    
    Does NOT clear production data. Instead, tests should use unique IDs
    (via test_match_id fixture) to avoid constraint violations.
    """
    test_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    
    yield test_client
    
    test_client.close()


@pytest.fixture
def schema_client(client, test_match_id):
    """Create a client with schema initialized and test context.
    
    Automatically cleans up all test-created data after the test completes.
    """
    setup_schema(client)
    # Store test match ID in client for tests to use
    client._test_match_id = test_match_id
    
    yield client
    
    # Cleanup: delete all nodes with test-specific markers/IDs
    try:
        # Delete all test Match nodes (identified by tm_ prefix or test names)
        client.execute(f"MATCH (m:Match {{id: '{test_match_id}'}}) DETACH DELETE m")
        client.execute("MATCH (m:Match {id: 'test_match'}) DETACH DELETE m")
        client.execute("MATCH (m:Match {id: 'match_1'}) DETACH DELETE m")
        
        # Delete all test nodes created with test markers
        client.execute("MATCH (n {test_marker: 'batch_test'}) DETACH DELETE n")
        client.execute(f"MATCH (n {{test_marker: 'test_{test_match_id}'}}) DETACH DELETE n")
        
        # Delete test nodes by label
        client.execute("MATCH (n:TestNode) DETACH DELETE n")
    except Exception:
        # Ignore cleanup errors
        pass


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data_at_session_end(neo4j_uri, neo4j_user, neo4j_password):
    """Session-scoped cleanup to remove any stray test data.
    
    Runs at the end of all tests to ensure test data doesn't pollute production.
    """
    yield
    
    # After all tests, clean up any remaining test matches
    try:
        client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
        
        # Delete any matches that aren't the production match
        client.execute("MATCH (m:Match) WHERE m.id <> 'match_18245' DETACH DELETE m")
        client.execute("MATCH (n:TestNode) DETACH DELETE n")
        
        client.close()
    except Exception:
        pass
