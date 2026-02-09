"""Neo4j schema setup."""
from .client import Neo4jClient


def setup_schema(client: Neo4jClient):
    """Create constraints and indexes for the graph."""
    queries = [
        # Node constraints
        (
            """
            CREATE CONSTRAINT match_id IF NOT EXISTS
            FOR (m:Match) REQUIRE m.id IS UNIQUE
            """,
            {},
        ),
        (
            """
            CREATE CONSTRAINT team_id IF NOT EXISTS
            FOR (t:Team) REQUIRE t.id IS UNIQUE
            """,
            {},
        ),
        (
            """
            CREATE CONSTRAINT player_id IF NOT EXISTS
            FOR (p:Player) REQUIRE p.id IS UNIQUE
            """,
            {},
        ),
        (
            """
            CREATE CONSTRAINT event_id IF NOT EXISTS
            FOR (e:Event) REQUIRE e.id IS UNIQUE
            """,
            {},
        ),
        (
            """
            CREATE CONSTRAINT possession_id IF NOT EXISTS
            FOR (pos:Possession) REQUIRE pos.id IS UNIQUE
            """,
            {},
        ),
        # Indexes for common queries
        ("CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.type)", {}),
        ("CREATE INDEX event_minute IF NOT EXISTS FOR (e:Event) ON (e.minute)", {}),
        (
            "CREATE INDEX event_timestamp IF NOT EXISTS FOR (e:Event) ON (e.timestamp)",
            {},
        ),
        (
            "CREATE INDEX possession_team IF NOT EXISTS FOR (p:Possession) ON (p.team_id)",
            {},
        ),
    ]
    client.execute_batch(queries)

    print("Schema setup complete")
