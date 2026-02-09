"""Data ingestion from StatsBomb JSON to Neo4j."""
import json
from pathlib import Path
from collections import defaultdict
from .client import Neo4jClient


class StatsBombIngestion:
    """Load StatsBomb event data into Neo4j."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def ingest(self, json_path: str, match_id: str):
        """Load a StatsBomb JSON file into Neo4j."""
        with open(json_path) as f:
            events = json.load(f)

        # Group events
        match_info = self._extract_match_info(events)
        teams_data = self._extract_teams(events)
        players_data = self._extract_players(events)
        possessions_data = self._extract_possessions(events)

        # Load in order
        self._load_match(match_id, match_info)
        self._load_teams(match_id, teams_data)
        self._load_players(teams_data, players_data)
        self._load_possessions(match_id, possessions_data)
        self._load_events(match_id, events, possessions_data)

        print(f"Loaded {len(events)} events into Neo4j")

    def _extract_match_info(self, events):
        """Extract match-level metadata."""
        first_event = events[0]
        return {
            "teams": set(),
            "periods": set(),
        }

    def _extract_teams(self, events):
        """Extract team info from Starting XI events."""
        teams = {}
        for event in events:
            if event["type"]["name"] == "Starting XI":
                team = event["team"]
                team_id = team["id"]
                if team_id not in teams:
                    teams[team_id] = {
                        "id": team_id,
                        "name": team["name"],
                        "formation": event.get("tactics", {}).get("formation"),
                        "players": [],
                    }
                # Add lineup
                if "tactics" in event and "lineup" in event["tactics"]:
                    teams[team_id]["players"] = [
                        {
                            "player_id": p["player"]["id"],
                            "position_id": p["position"]["id"],
                            "position_name": p["position"]["name"],
                            "jersey_number": p.get("jersey_number"),
                        }
                        for p in event["tactics"]["lineup"]
                    ]
        return teams

    def _extract_players(self, events):
        """Extract all unique players."""
        players = {}
        for event in events:
            if "player" in event and event["player"] is not None:
                p = event["player"]
                player_id = p["id"]
                if player_id not in players:
                    players[player_id] = {
                        "id": player_id,
                        "name": p["name"],
                    }
        return players

    def _extract_possessions(self, events):
        """Group events by possession."""
        possessions = defaultdict(list)
        for event in events:
            pos_id = event["possession"]
            possessions[pos_id].append(event)
        return possessions

    def _load_match(self, match_id: str, match_info):
        """Create Match node."""
        cypher = """
        CREATE (m:Match {
            id: $match_id,
            loaded_at: datetime()
        })
        """
        self.client.execute(cypher, {"match_id": match_id})

    def _load_teams(self, match_id: str, teams_data):
        """Create Team nodes and connect to Match."""
        for team_id, team_info in teams_data.items():
            cypher = """
            MATCH (m:Match {id: $match_id})
            CREATE (t:Team {
                id: $team_id,
                name: $name,
                formation: $formation
            })
            CREATE (t)-[:IN_MATCH]->(m)
            """
            self.client.execute(
                cypher,
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "name": team_info["name"],
                    "formation": team_info["formation"],
                },
            )

    def _load_players(self, teams_data, players_data):
        """Create Player nodes and connect to Teams."""
        queries = []
        for team_id, team_info in teams_data.items():
            for player_pos in team_info["players"]:
                player_id = player_pos["player_id"]
                player_info = players_data.get(player_id, {})

                cypher = """
                MATCH (t:Team {id: $team_id})
                CREATE (p:Player {
                    id: $player_id,
                    name: $name,
                    jersey_number: $jersey_number,
                    position: $position
                })
                CREATE (p)-[:PLAYS_FOR]->(t)
                """
                queries.append(
                    (
                        cypher,
                        {
                            "team_id": team_id,
                            "player_id": player_id,
                            "name": player_info.get("name", "Unknown"),
                            "jersey_number": player_pos.get("jersey_number"),
                            "position": player_pos["position_name"],
                        },
                    )
                )
        self.client.execute_batch(queries)

    def _load_possessions(self, match_id: str, possessions_data):
        """Create Possession nodes."""
        queries = []
        for pos_id, events in possessions_data.items():
            if not events:
                continue

            first_event = events[0]
            last_event = events[-1]

            team_id = first_event["possession_team"]["id"]

            cypher = """
            MATCH (m:Match {id: $match_id})
            CREATE (pos:Possession {
                id: $pos_id,
                team_id: $team_id,
                start_minute: $start_minute,
                end_minute: $end_minute,
                event_count: $event_count
            })
            CREATE (pos)-[:IN_MATCH]->(m)
            """
            queries.append(
                (
                    cypher,
                    {
                        "match_id": match_id,
                        "pos_id": pos_id,
                        "team_id": team_id,
                        "start_minute": first_event["minute"],
                        "end_minute": last_event["minute"],
                        "event_count": len(events),
                    },
                )
            )
        self.client.execute_batch(queries)

    def _load_events(self, match_id: str, events, possessions_data):
        """Create Event nodes with relationships."""
        queries = []

        for idx, event in enumerate(events):
            event_id = event["id"]
            event_type = event["type"]["name"]
            period = event["period"]
            minute = event["minute"]
            second = event["second"]
            timestamp = event.get("timestamp", "")

            # Create event node with type label using apoc
            cypher = """
            MATCH (m:Match {id: $match_id})
            CALL apoc.create.node(['Event', $event_type], {
                id: $event_id,
                type: $event_type,
                period: $period,
                minute: $minute,
                second: $second,
                timestamp: $timestamp,
                possession_id: $possession_id
            }) YIELD node as e
            CREATE (e)-[:IN_MATCH]->(m)
            """
            queries.append(
                (
                    cypher,
                    {
                        "match_id": match_id,
                        "event_id": event_id,
                        "event_type": event_type,
                        "period": period,
                        "minute": minute,
                        "second": second,
                        "timestamp": timestamp,
                        "possession_id": event["possession"],
                    },
                )
            )

            # Link to possession
            pos_cypher = """
            MATCH (e:Event {id: $event_id})
            MATCH (pos:Possession {id: $pos_id})
            CREATE (pos)-[:CONTAINS]->(e)
            """
            queries.append((pos_cypher, {"event_id": event_id, "pos_id": event["possession"]}))

            # Link to player if exists
            if "player" in event:
                player_cypher = """
                MATCH (e:Event {id: $event_id})
                MATCH (p:Player {id: $player_id})
                CREATE (e)-[:BY]->(p)
                """
                queries.append(
                    (player_cypher, {"event_id": event_id, "player_id": event["player"]["id"]})
                )

            # Handle event type specifics
            if event_type == "Pass" and "pass" in event:
                pass_data = event["pass"]
                if "recipient" in pass_data:
                    pass_cypher = """
                    MATCH (e:Event {id: $event_id})
                    MATCH (p:Player {id: $recipient_id})
                    CREATE (e)-[:TO_PLAYER]->(p)
                    """
                    queries.append(
                        (
                            pass_cypher,
                            {
                                "event_id": event_id,
                                "recipient_id": pass_data["recipient"]["id"],
                            },
                        )
                    )

            elif event_type == "Shot" and "shot" in event:
                shot_data = event["shot"]
                # Store xG value on event
                cypher = """
                MATCH (e:Event {id: $event_id})
                SET e.xg = $xg,
                    e.outcome = $outcome
                """
                queries.append(
                    (
                        cypher,
                        {
                            "event_id": event_id,
                            "xg": shot_data.get("statsbomb_xg"),
                            "outcome": shot_data.get("outcome", {}).get("name"),
                        },
                    )
                )

        # Link events in temporal order per possession
        for pos_id, pos_events in possessions_data.items():
            for i in range(len(pos_events) - 1):
                curr_id = pos_events[i]["id"]
                next_id = pos_events[i + 1]["id"]
                next_cypher = """
                MATCH (e:Event {id: $curr_id})
                MATCH (next:Event {id: $next_id})
                CREATE (e)-[:NEXT]->(next)
                """
                queries.append((next_cypher, {"curr_id": curr_id, "next_id": next_id}))

        self.client.execute_batch(queries)
