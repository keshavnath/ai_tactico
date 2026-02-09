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


def test_client_execute(client):
    """Test that client can execute queries."""
    client.execute("CREATE (n:TestNode {value: 'test'})")
    
    result = client.query("MATCH (n:TestNode) RETURN n.value as value")
    assert len(result) == 1
    assert result[0]["value"] == "test"


def test_client_execute_batch(client):
    """Test batch query execution."""
    queries = [
        ("CREATE (n:Node1 {id: 1})", {}),
        ("CREATE (n:Node2 {id: 2})", {}),
        ("CREATE (n:Node3 {id: 3})", {}),
    ]
    
    client.execute_batch(queries)
    
    result = client.query("MATCH (n) RETURN count(n) as count")
    assert result[0]["count"] == 3


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
