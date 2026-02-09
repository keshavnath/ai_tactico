"""Tests for Neo4j client."""
import pytest
from src.db import Neo4jClient


def test_client_connects(neo4j_uri, neo4j_user, neo4j_password):
    """Test that client can connect to Neo4j."""
    client = Neo4jClient(neo4j_uri, neo4j_user, neo4j_password)
    
    # Should not raise
    result = client.query("RETURN 1 as value")
    assert result[0]["value"] == 1
    
    client.close()


def test_client_execute(client, test_match_id):
    """Test that client can execute queries."""
    test_marker = f"test_{test_match_id}"
    client.execute(f"CREATE (n:TestNode {{value: 'test', marker: '{test_marker}'}})")
    
    result = client.query(f"MATCH (n:TestNode {{marker: '{test_marker}'}}) RETURN n.value as value")
    assert len(result) == 1
    assert result[0]["value"] == "test"
    
    # Note: Cleanup is handled by parent fixture if needed, but this test
    # doesn't use schema_client so manual cleanup is necessary here
    client.execute(f"MATCH (n:TestNode {{marker: '{test_marker}'}}) DETACH DELETE n")


def test_client_execute_batch(client):
    """Test batch query execution."""
    queries = [
        ("CREATE (n:Node1 {id: 1, test_marker: 'batch_test'})", {}),
        ("CREATE (n:Node2 {id: 2, test_marker: 'batch_test'})", {}),
        ("CREATE (n:Node3 {id: 3, test_marker: 'batch_test'})", {}),
    ]
    
    client.execute_batch(queries)
    
    # Count only test nodes (not all nodes in database)
    result = client.query("MATCH (n {test_marker: 'batch_test'}) RETURN count(n) as count")
    assert result[0]["count"] == 3
    
    # Cleanup test nodes
    client.execute("MATCH (n {test_marker: 'batch_test'}) DETACH DELETE n")


def test_client_with_parameters(client):
    """Test query execution with parameters."""
    params = {"name": "Alice", "age": 30}
    client.execute(
        "CREATE (n:Person {name: $name, age: $age})",
        params
    )
    
    result = client.query(
        "MATCH (n:Person {name: $name}) RETURN n.age as age",
        {"name": "Alice"}
    )
    assert result[0]["age"] == 30
