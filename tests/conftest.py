"""Pytest fixtures and configuration."""
import pytest
import os
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
def client(neo4j_uri, neo4j_user, neo4j_password):
    """Create a test Neo4j client with clean database.
    
    Clears all data before and after test to prevent cross-test pollution.
    Safe to use with production data since cleanup is scoped per test.
    """
    test_client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    
    # Clear database before test
    test_client.execute("MATCH (n) DETACH DELETE n")
    
    yield test_client
    
    # Cleanup after test
    test_client.execute("MATCH (n) DETACH DELETE n")
    test_client.close()


@pytest.fixture
def schema_client(client):
    """Create a client with schema initialized."""
    setup_schema(client)
    return client
