"""Initialize database and load data."""
import argparse
import os
from pathlib import Path
from src.db import Neo4jClient, setup_schema, StatsBombIngestion


def main():
    parser = argparse.ArgumentParser(description="Load StatsBomb data into Neo4j")
    parser.add_argument(
        "--uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI",
    )
    parser.add_argument(
        "--user",
        default=os.getenv("NEO4J_USER", "neo4j"),
        help="Neo4j username",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("NEO4J_PASSWORD", "password"),
        help="Neo4j password",
    )
    parser.add_argument(
        "--data-file",
        required=True,
        help="Path to StatsBomb JSON file",
    )
    parser.add_argument(
        "--match-id",
        default="match_001",
        help="Unique identifier for this match",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Clear existing data and indexes before loading (full rebuild)",
    )

    args = parser.parse_args()

    client = Neo4jClient(args.uri, args.user, args.password)

    try:
        if args.overwrite:
            print("Clearing existing data and constraints...")
            
            # Drop all indexes first
            try:
                indexes = client.query("SHOW INDEXES")
                for idx in indexes:
                    # Try different field name variations across Neo4j versions
                    idx_name = idx.get("name") or idx.get("indexName") or idx.get("Index name")
                    if idx_name and not idx_name.startswith("__"):  # Skip system indexes
                        try:
                            client.execute(f"DROP INDEX `{idx_name}` IF EXISTS")
                            print(f"  Dropped index: {idx_name}")
                        except Exception as e:
                            print(f"  Note: Could not drop index {idx_name}: {str(e)[:80]}")
            except Exception as e:
                print(f"  Note: Could not query indexes: {str(e)[:80]}")
            
            # Drop all constraints
            try:
                constraints = client.query("SHOW CONSTRAINTS")
                for const in constraints:
                    # Try different field name variations across Neo4j versions
                    const_name = const.get("name") or const.get("constraintName") or const.get("Constraint name")
                    if const_name and not const_name.startswith("__"):  # Skip system constraints
                        try:
                            client.execute(f"DROP CONSTRAINT `{const_name}` IF EXISTS")
                            print(f"  Dropped constraint: {const_name}")
                        except Exception as e:
                            print(f"  Note: Could not drop constraint {const_name}: {str(e)[:80]}")
            except Exception as e:
                print(f"  Note: Could not query constraints: {str(e)[:80]}")
            
            # Clear all data
            print("Deleting all nodes and relationships...")
            client.execute("MATCH (n) DETACH DELETE n")
            print("Clear complete. Setting up fresh schema...")

        print("Setting up schema...")
        setup_schema(client)

        print(f"Loading data from {args.data_file}...")
        ingestion = StatsBombIngestion(client)
        ingestion.ingest(args.data_file, args.match_id)

        print("Data load completed successfully")

    finally:
        client.close()

if __name__ == "__main__":
    main()
