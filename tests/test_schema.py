"""Tests for Neo4j schema setup."""
from src.db import setup_schema


def test_schema_creates_constraints(client):
    """Test that schema creates all required constraints."""
    setup_schema(client)
    
    # Query existing constraints
    constraints = client.query("""
    SHOW CONSTRAINTS
    """)
    
    # Should have constraints for Match, Team, Player, Event, Possession
    constraint_names = {c.get("name") for c in constraints}
    
    assert "match_id" in constraint_names or any("match" in str(c) for c in constraints)
    assert "team_id" in constraint_names or any("team" in str(c) for c in constraints)
    assert "player_id" in constraint_names or any("player" in str(c) for c in constraints)
    assert "event_id" in constraint_names or any("event" in str(c) for c in constraints)


def test_schema_creates_indexes(client):
    """Test that schema creates required indexes."""
    setup_schema(client)
    
    # Query existing indexes
    indexes = client.query("""
    SHOW INDEXES WHERE type = 'RANGE'
    """)
    
    # Should have indexes for common queries
    index_names = [idx.get("name") for idx in indexes]
    
    # At least some indexes should exist for event queries
    assert len(index_names) > 0


def test_constraint_prevents_duplicates(schema_client):
    """Test that uniqueness constraint prevents duplicate node IDs."""
    # Create first match
    schema_client.execute("""
    CREATE (m:Match {id: 'match_1', loaded_at: datetime()})
    """)
    
    # Try to create duplicate
    try:
        schema_client.execute("""
        CREATE (m:Match {id: 'match_1', loaded_at: datetime()})
        """)
        # Should raise an error
        assert False, "Expected constraint violation"
    except Exception as e:
        assert "ConstraintValidationFailed" in str(e) or "already exists" in str(e)
