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
        "--clear",
        action="store_true",
        help="Clear existing data before loading",
    )

    args = parser.parse_args()

    client = Neo4jClient(args.uri, args.user, args.password)

    try:
        if args.clear:
            print("Clearing existing data...")
            client.execute("MATCH (n) DETACH DELETE n")

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
