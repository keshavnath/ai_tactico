"""Data ingestion from StatsBomb JSON to Neo4j with comprehensive tactical data capture."""
import json
from pathlib import Path
from collections import defaultdict
from .client import Neo4jClient


class StatsBombIngestion:
    """Load StatsBomb event data into Neo4j with all tactical information."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def ingest(self, json_path: str, match_id: str):
        """Load a StatsBomb JSON file into Neo4j with comprehensive data capture."""
        with open(json_path) as f:
            events = json.load(f)

        print(f"Ingesting {len(events)} events with comprehensive tactical data...")

        # Extract metadata
        match_info = self._extract_match_info(events)
        teams_data = self._extract_teams(events)
        players_data = self._extract_players(events)
        possessions_data = self._extract_possessions(events)

        # Load in order
        self._load_match(match_id, match_info)
        self._load_teams(match_id, teams_data)
        self._load_players(teams_data, players_data)
        self._load_possessions(match_id, possessions_data)
        self._load_events_with_tactics(match_id, events, possessions_data)

        print(f"✓ Loaded {len(events)} events with all tactical properties")

    def _extract_match_info(self, events):
        """Extract match-level metadata."""
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

    def _load_events_with_tactics(self, match_id: str, events, possessions_data):
        """Create Event nodes with COMPREHENSIVE tactical data."""
        queries = []

        for idx, event in enumerate(events):
            event_id = event["id"]
            event_type = event["type"]["name"]
            period = event["period"]
            minute = event["minute"]
            second = event["second"]
            timestamp = event.get("timestamp", "")
            possession_id = event["possession"]

            # Extract common properties
            location = event.get("location")
            location_x = location[0] if location else None
            location_y = location[1] if location else None

            team_id = event["team"]["id"] if "team" in event else None
            team_name = event["team"]["name"] if "team" in event else None
            player_id = event["player"]["id"] if "player" in event else None
            player_name = event["player"]["name"] if "player" in event else None

            # Position data
            position_id = event.get("position", {}).get("id")
            position_name = event.get("position", {}).get("name")

            # Play pattern
            play_pattern = event.get("play_pattern", {}).get("name")

            # Under pressure flag
            under_pressure = event.get("under_pressure", False)

            # Duration (common to many events)
            duration = event.get("duration")

            # Initialize event properties dict
            event_props = {
                "id": event_id,
                "type": event_type,
                "period": period,
                "minute": minute,
                "second": second,
                "timestamp": timestamp,
                "possession_id": possession_id,
                "location_x": location_x,
                "location_y": location_y,
                "team_id": team_id,
                "team_name": team_name,
                "player_id": player_id,
                "player_name": player_name,
                "position_id": position_id,
                "position_name": position_name,
                "play_pattern": play_pattern,
                "under_pressure": under_pressure,
                "duration": duration,
            }

            # ===== EVENT TYPE SPECIFIC DATA =====
            
            # PASS
            if event_type == "Pass" and "pass" in event:
                pass_data = event["pass"]
                event_props.update({
                    "pass_outcome": pass_data.get("outcome", {}).get("name"),
                    "pass_length": pass_data.get("length"),
                    "pass_angle": pass_data.get("angle"),
                    "pass_end_location_x": pass_data.get("end_location", [None, None])[0],
                    "pass_end_location_y": pass_data.get("end_location", [None, None])[1],
                    "pass_height_id": pass_data.get("height", {}).get("id"),
                    "pass_height_name": pass_data.get("height", {}).get("name"),
                    "pass_body_part_id": pass_data.get("body_part", {}).get("id"),
                    "pass_body_part_name": pass_data.get("body_part", {}).get("name"),
                    "pass_cut_back": pass_data.get("cut_back", False),
                    "pass_cross": pass_data.get("cross", False),
                    "pass_deflected": pass_data.get("deflected", False),
                    "pass_through_ball": pass_data.get("through_ball", False),
                    "pass_in_aerial": pass_data.get("in_aerial", False),
                    "pass_straight": pass_data.get("straight", False),
                    "pass_air_pass": pass_data.get("air_pass", False),
                    "pass_goal_assist": pass_data.get("goal_assist", False),
                    "pass_assisted_shot_id": pass_data.get("assisted_shot_id"),
                    "pass_key_pass_id": pass_data.get("key_pass_id"),
                    "pass_recipient_id": pass_data.get("recipient", {}).get("id"),
                    "pass_recipient_name": pass_data.get("recipient", {}).get("name"),
                })

            # SHOT
            elif event_type == "Shot" and "shot" in event:
                shot_data = event["shot"]
                event_props.update({
                    "shot_outcome": shot_data.get("outcome", {}).get("name"),
                    "shot_xg": shot_data.get("statsbomb_xg"),
                    "shot_xg2": shot_data.get("statsbomb_xg2"),
                    "shot_technique_id": shot_data.get("technique", {}).get("id"),
                    "shot_technique_name": shot_data.get("technique", {}).get("name"),
                    "shot_body_part_id": shot_data.get("body_part", {}).get("id"),
                    "shot_body_part_name": shot_data.get("body_part", {}).get("name"),
                    "shot_key_pass_id": shot_data.get("key_pass_id"),
                    "shot_one_on_one": shot_data.get("one_on_one", False),
                    "shot_deflected": shot_data.get("deflected", False),
                    "shot_freeze_frame": len(shot_data.get("freeze_frame", [])),
                    "end_location_x": shot_data.get("end_location", [None, None, None])[0],
                    "end_location_y": shot_data.get("end_location", [None, None, None])[1],
                })

            # PRESSURE
            elif event_type == "Pressure":
                event_props["pressure_duration"] = duration

            # CARRY
            elif event_type == "Carry" and "carry" in event:
                carry_data = event["carry"]
                event_props.update({
                    "end_location_x": carry_data.get("end_location", [None, None])[0],
                    "end_location_y": carry_data.get("end_location", [None, None])[1],
                })

            # DUEL
            elif event_type == "Duel" and "duel" in event:
                duel_data = event["duel"]
                event_props.update({
                    "duel_outcome": duel_data.get("outcome", {}).get("name"),
                    "duel_counterpress": event.get("counterpress", False),
                })

            # FOUL COMMITTED
            elif event_type == "Foul Committed" and "foul_committed" in event:
                foul_data = event["foul_committed"]
                event_props.update({
                    "foul_outcome": foul_data.get("outcome", {}).get("name"),
                    "foul_penalty": foul_data.get("penalty", False),
                    "foul_red_card": foul_data.get("red_card", False),
                    "foul_yellow_card": foul_data.get("yellow_card", False),
                })

            # BALL RECEIPT*
            elif event_type == "Ball Receipt*":
                event_props["ball_receipt"] = True

            # BALL RECOVERY
            elif event_type == "Ball Recovery":
                event_props["ball_recovery"] = True

            # BLOCK
            elif event_type == "Block" and "block" in event:
                block_data = event["block"]
                event_props.update({
                    "block_deflection": block_data.get("deflection", False),
                    "block_offensive": block_data.get("offensive", False),
                    "block_save": block_data.get("save", False),
                })

            # OUT
            elif event_type == "Out":
                event_props["out"] = event.get("out", False)

            # TACKLE
            elif event_type == "Tackle" and "tackle" in event:
                tackle_data = event["tackle"]
                event_props.update({
                    "tackle_outcome": tackle_data.get("outcome", {}).get("name"),
                    "tackle_defender_id": tackle_data.get("defender", {}).get("id"),
                    "tackle_defender_name": tackle_data.get("defender", {}).get("name"),
                })

            # INTERCEPTION
            elif event_type == "Interception" and "interception" in event:
                interception_data = event["interception"]
                event_props["interception_outcome"] = interception_data.get("outcome", {}).get(
                    "name"
                )

            # CLEARANCE
            elif event_type == "Clearance" and "clearance" in event:
                clearance_data = event["clearance"]
                event_props.update({
                    "clearance_body_part_id": clearance_data.get("body_part", {}).get("id"),
                    "clearance_body_part_name": clearance_data.get("body_part", {}).get("name"),
                    "clearance_head": clearance_data.get("head", False),
                    "clearance_other": clearance_data.get("other", False),
                })

            # DISPOSSESSED
            elif event_type == "Dispossessed" and "dispossessed" in event:
                event_props["dispossessed"] = True

            # 50/50
            elif event_type == "50/50":
                event_props["fifty_fifty"] = True

            # GOAL KEEPER
            elif event_type == "Goal Keeper" and "goalkeeper" in event:
                gk_data = event["goalkeeper"]
                event_props.update({
                    "gk_outcome": gk_data.get("outcome", {}).get("name"),
                    "gk_position_id": gk_data.get("position", {}).get("id"),
                    "gk_position_name": gk_data.get("position", {}).get("name"),
                    "gk_technique_id": gk_data.get("technique", {}).get("id"),
                    "gk_technique_name": gk_data.get("technique", {}).get("name"),
                    "gk_body_part_id": gk_data.get("body_part", {}).get("id"),
                    "gk_body_part_name": gk_data.get("body_part", {}).get("name"),
                })

            # Create event node - standard Neo4j (no APOC required)
            # Store event type as a property, not as a dynamic label
            set_clauses = []
            for key, value in event_props.items():
                if key != "id":  # id is set in create
                    set_clauses.append(f"e.{key} = ${key}")

            set_statement = ", ".join(set_clauses) if set_clauses else ""
            if set_statement:
                set_statement = "\nSET " + set_statement

            cypher = f"""
            MATCH (m:Match {{id: $match_id}})
            CREATE (e:Event {{id: $id}})-[:IN_MATCH]->(m)
            {set_statement}
            """
            queries.append((cypher, {"match_id": match_id, **event_props}))

            # Link to possession
            pos_cypher = """
            MATCH (e:Event {id: $event_id})
            MATCH (pos:Possession {id: $pos_id})
            CREATE (pos)-[:CONTAINS]->(e)
            """
            queries.append((pos_cypher, {"event_id": event_id, "pos_id": possession_id}))

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
