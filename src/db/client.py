"""Neo4j client wrapper."""
from neo4j import GraphDatabase


class Neo4jClient:
    """Simple Neo4j connection manager."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def query(self, cypher: str, params: dict = None):
        """Execute a query and return results."""
        with self.driver.session() as session:
            return session.run(cypher, params or {}).data()

    def execute(self, cypher: str, params: dict = None):
        """Execute a query without returning results."""
        with self.driver.session() as session:
            session.run(cypher, params or {})

    def execute_batch(self, queries: list[tuple]):
        """Execute multiple queries. Each tuple is (cypher, params)."""
        with self.driver.session() as session:
            for cypher, params in queries:
                session.run(cypher, params or {})
