"""Neo4j schema setup with comprehensive indexes for tactical analysis."""
from .client import Neo4jClient


def setup_schema(client: Neo4jClient):
    """Create constraints and indexes for comprehensive tactical graph."""
    queries = [
        # ===== UNIQUE CONSTRAINTS =====
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
        
        # ===== CORE EVENT INDEXES =====
        ("CREATE INDEX event_type IF NOT EXISTS FOR (e:Event) ON (e.type)", {}),
        ("CREATE INDEX event_minute IF NOT EXISTS FOR (e:Event) ON (e.minute)", {}),
        ("CREATE INDEX event_period IF NOT EXISTS FOR (e:Event) ON (e.period)", {}),
        ("CREATE INDEX event_timestamp IF NOT EXISTS FOR (e:Event) ON (e.timestamp)", {}),
        
        # ===== SPATIAL INDEXES (Location-based analysis) =====
        ("CREATE INDEX event_location_x IF NOT EXISTS FOR (e:Event) ON (e.location_x)", {}),
        ("CREATE INDEX event_location_y IF NOT EXISTS FOR (e:Event) ON (e.location_y)", {}),
        ("CREATE INDEX event_end_location_x IF NOT EXISTS FOR (e:Event) ON (e.end_location_x)", {}),
        ("CREATE INDEX event_end_location_y IF NOT EXISTS FOR (e:Event) ON (e.end_location_y)", {}),
        
        # ===== TACTICAL INDEXES (Player positions & strategies) =====
        ("CREATE INDEX player_position IF NOT EXISTS FOR (p:Player) ON (p.position_name)", {}),
        ("CREATE INDEX event_position IF NOT EXISTS FOR (e:Event) ON (e.position_name)", {}),
        ("CREATE INDEX event_team IF NOT EXISTS FOR (e:Event) ON (e.team_id)", {}),
        ("CREATE INDEX event_player IF NOT EXISTS FOR (e:Event) ON (e.player_id)", {}),
        
        # ===== PASS ANALYSIS INDEXES =====
        ("CREATE INDEX pass_outcome IF NOT EXISTS FOR (e:Event) ON (e.pass_outcome)", {}),
        ("CREATE INDEX pass_cut_back IF NOT EXISTS FOR (e:Event) ON (e.pass_cut_back)", {}),
        ("CREATE INDEX pass_cross IF NOT EXISTS FOR (e:Event) ON (e.pass_cross)", {}),
        ("CREATE INDEX pass_through_ball IF NOT EXISTS FOR (e:Event) ON (e.pass_through_ball)", {}),
        ("CREATE INDEX pass_goal_assist IF NOT EXISTS FOR (e:Event) ON (e.pass_goal_assist)", {}),
        ("CREATE INDEX pass_assisted_shot IF NOT EXISTS FOR (e:Event) ON (e.pass_assisted_shot_id)", {}),
        ("CREATE INDEX pass_body_part IF NOT EXISTS FOR (e:Event) ON (e.pass_body_part_name)", {}),
        ("CREATE INDEX pass_height IF NOT EXISTS FOR (e:Event) ON (e.pass_height_name)", {}),
        ("CREATE INDEX pass_length IF NOT EXISTS FOR (e:Event) ON (e.pass_length)", {}),
        ("CREATE INDEX pass_angle IF NOT EXISTS FOR (e:Event) ON (e.pass_angle)", {}),
        
        # ===== PRESSURE ANALYSIS INDEXES =====
        ("CREATE INDEX pressure_duration IF NOT EXISTS FOR (e:Event) ON (e.pressure_duration)", {}),
        ("CREATE INDEX under_pressure IF NOT EXISTS FOR (e:Event) ON (e.under_pressure)", {}),
        
        # ===== SHOT ANALYSIS INDEXES =====
        ("CREATE INDEX shot_outcome IF NOT EXISTS FOR (e:Event) ON (e.shot_outcome)", {}),
        ("CREATE INDEX shot_xg IF NOT EXISTS FOR (e:Event) ON (e.shot_xg)", {}),
        ("CREATE INDEX shot_tech IF NOT EXISTS FOR (e:Event) ON (e.shot_technique_name)", {}),
        ("CREATE INDEX shot_body_part IF NOT EXISTS FOR (e:Event) ON (e.shot_body_part_name)", {}),
        ("CREATE INDEX shot_key_pass IF NOT EXISTS FOR (e:Event) ON (e.shot_key_pass_id)", {}),
        
        # ===== DUEL ANALYSIS INDEXES =====
        ("CREATE INDEX duel_outcome IF NOT EXISTS FOR (e:Event) ON (e.duel_outcome)", {}),
        ("CREATE INDEX duel_counterpress IF NOT EXISTS FOR (e:Event) ON (e.duel_counterpress)", {}),
        
        # ===== POSSESSION & FLOW INDEXES =====
        ("CREATE INDEX possession_team IF NOT EXISTS FOR (pos:Possession) ON (pos.team_id)", {}),
        ("CREATE INDEX event_possession IF NOT EXISTS FOR (e:Event) ON (e.possession_id)", {}),
        
        # ===== PLAY PATTERN INDEXES =====
        ("CREATE INDEX play_pattern IF NOT EXISTS FOR (e:Event) ON (e.play_pattern)", {}),
        
        # ===== DURATION ANALYSIS INDEXES (Carry, Duel dynamics) =====
        ("CREATE INDEX event_duration IF NOT EXISTS FOR (e:Event) ON (e.duration)", {}),
    ]
    client.execute_batch(queries)

    print("✓ Schema setup complete with comprehensive tactical indexes")
    print("  - Location-based: spatial coordinates for buildup analysis")
    print("  - Pass analysis: end_location, height, length, angle, assists")
    print("  - Pressure: duration, under_pressure flag")
    print("  - Shots: xG, outcome, technique, key_pass")
    print("  - Duels: outcome, counterpress dynamics")
