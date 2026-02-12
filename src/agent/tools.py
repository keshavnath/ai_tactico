"""Tactical analysis tools for graph traversal.

Pure functions for querying the Neo4j knowledge graph and computing tactical metrics.
Each tool's docstring is automatically extracted and serves as the prompt for the agent,
explaining when to use it, what it needs, and what to expect.

Works like MCP: docstrings are the single source of truth for tool descriptions.
"""
import inspect
from src.db import Neo4jClient
from .schemas import PossessionChain, PassData, FormationSnapshot, ToolResult
from typing import Optional, Any
import re


def find_events(
    db: Neo4jClient,
    event_type: Optional[str] = None,
    minute: Optional[int] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
    player: Optional[str] = None,
    team: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 20,
) -> ToolResult:
    """Find events by type, time, player, team, or outcome.
    
    Parameters:
    - event_type: Pass, Shot, Tackle, Duel, Pressure, Carry, Block, Interception, Clearance, Foul Committed, Goal Keeper, Ball Recovery, Ball Receipt*, Dispossessed, 50/50, Out
    - minute_min/minute_max: time window
    - player: player name substring
    - team: team name substring
    - outcome: Goal, Miss, Saved, etc.
    - limit: max results
    
    Examples: find_events(event_type="Shot", player="Benzema") or find_events(event_type="Tackle", minute_min=30, minute_max=45)
    """
    params = {}
    
    # TRANSLATION: If user asks for "Goal" as event_type, convert to Shot + Goal outcome
    # This handles the natural language confusion where users think "Goal" is an event type
    if event_type and event_type.lower() == "goal":
        event_type = "Shot"
        if not outcome:
            outcome = "Goal"
    
    # Build MATCH clause for event (all events are :Event nodes with type property)
    match_clause = "MATCH (event:Event)"
    if event_type:
        where_type_condition = f"event.type = '{event_type}'"
    
    # Build WHERE conditions
    where_conditions = []
    if event_type:
        where_conditions.append(where_type_condition)
    if minute is not None:
        where_conditions.append(f"event.minute = {minute}")
    if minute_min is not None:
        where_conditions.append(f"event.minute >= {minute_min}")
    if minute_max is not None:
        where_conditions.append(f"event.minute <= {minute_max}")
    
    # Check for outcome in event-type-specific fields
    if outcome:
        # For shots, check shot_outcome
        outcome_checks = [
            f"event.shot_outcome = $outcome",  # Shot events
            f"event.pass_outcome = $outcome",  # Pass events
            f"event.duel_outcome = $outcome",  # Duel events
            f"event.foul_outcome = $outcome",  # Foul events
            f"event.tackle_outcome = $outcome",  # Tackle events
            f"event.interception_outcome = $outcome",  # Interception events
        ]
        where_conditions.append(f"({' OR '.join(outcome_checks)})")
        params["outcome"] = outcome
    
    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)
    
    # Add player filter if specified (now using flattened player_name property)
    if player:
        params["player"] = player.lower()
        if where_clause:
            where_clause += f"\nAND LOWER(event.player_name) CONTAINS $player"
        else:
            where_clause = f"WHERE LOWER(event.player_name) CONTAINS $player"
    
    # Add team filter if specified (now using flattened team_name property)
    if team:
        params["team"] = team.lower()
        if where_clause:
            where_clause += f"\nAND LOWER(event.team_name) CONTAINS $team"
        else:
            where_clause = f"WHERE LOWER(event.team_name) CONTAINS $team"
    
    query = f"""{match_clause}
{where_clause}
RETURN 
    event.id as event_id,
    event.type as event_type,
    event.minute as minute,
    event.period as period,
    COALESCE(event.player_name, 'N/A') as player,
    COALESCE(event.team_name, 'N/A') as team,
    COALESCE(event.shot_outcome, event.pass_outcome, event.duel_outcome, 'N/A') as outcome,
    event.shot_key_pass_id as key_pass_id,
    event.shot_xg as xg,
    event.location_x as location_x,
    event.location_y as location_y
ORDER BY event.minute ASC
LIMIT {limit}"""
    
    try:
        results = db.query(query, params)
        
        if not results:
            return ToolResult(success=False, error="No events found matching criteria")
        
        events = [
            {
                "event_id": r["event_id"],
                "type": r["event_type"],
                "minute": r["minute"],
                "period": r["period"],
                "player": r["player"],
                "team": r["team"],
                "outcome": r["outcome"],
                **( {"key_pass_id": r["key_pass_id"]} if r.get("key_pass_id") else {}),
                **( {"xg": round(r["xg"], 3)} if r.get("xg") else {}),
                **( {"location": (r["location_x"], r["location_y"])} if r.get("location_x") else {}),
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=events, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def find_goals(
    db: Neo4jClient,
    team: Optional[str] = None,
    player: Optional[str] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
) -> ToolResult:
    """Find all goals in match, optionally by team, player, or time window.
    
    Parameters:
    - team: team name substring
    - player: player name substring (scorer)
    - minute_min/minute_max: time window
    
    Returns goals with: event_id, minute, scorer, team, key_pass_id.
    
    Examples: find_goals(player="Benzema") or find_goals(team="Real Madrid", minute_min=0, minute_max=20)
    """
    where_conditions = []
    params = {}
    
    # Build WHERE conditions - ensure we only get Shot events
    where_conditions.append("event.type = 'Shot'")
    where_conditions.append("event.shot_outcome = 'Goal'")
    
    if minute_min is not None:
        where_conditions.append(f"event.minute >= {minute_min}")
    if minute_max is not None:
        where_conditions.append(f"event.minute <= {minute_max}")
    
    where_clause = "WHERE " + " AND ".join(where_conditions)
    
    # Add player filter if specified (using flattened player_name property)
    if player:
        params["player"] = player.lower()
        where_clause += f"\nAND LOWER(event.player_name) CONTAINS $player"
    
    # Add team filter if specified (using flattened team_name property)
    if team:
        params["team"] = team.lower()
        where_clause += f"\nAND LOWER(event.team_name) CONTAINS $team"
    
    query = f"""MATCH (event:Event)
{where_clause}
RETURN 
    event.id as event_id,
    event.minute as minute,
    event.period as period,
    COALESCE(event.player_name, 'Unknown') as scorer,
    COALESCE(event.team_name, 'Unknown') as team,
    event.shot_key_pass_id as key_pass_id
ORDER BY event.minute ASC"""
    
    try:
        results = db.query(query, params)
        
        if not results:
            return ToolResult(success=False, error="No goals found matching criteria")
        
        goals = [
            {
                "event_id": r["event_id"],
                "minute": r["minute"],
                "period": r["period"],
                "scorer": r["scorer"],
                "team": r["team"],
                "key_pass_id": r["key_pass_id"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=goals, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_event_context(
    db: Neo4jClient,
    event_id: str,
) -> ToolResult:
    """Get full buildup (possession chain) leading to an event - detailed tactical analysis.
    
    Parameters:
    - event_id: event ID from find_events() or find_goals()
    
    Returns: complete passes leading up to the event with all tactical details (coordinates, angles, distances).
    Use for: detailed tactical breakdowns, comprehensive analysis, understanding spatial flow.
    """
    query = """
    MATCH (target_event:Event {id: $event_id})
    MATCH (pos:Possession)-[:CONTAINS]->(target_event)
    MATCH (pos)-[:CONTAINS]->(event:Event)
    WHERE event.type = 'Pass'
    WITH target_event, event
    ORDER BY event.minute ASC, event.second ASC
    RETURN 
        target_event.type as event_type,
        target_event.minute as event_minute,
        target_event.period as event_period,
        COALESCE(target_event.shot_outcome, target_event.pass_outcome, target_event.duel_outcome) as event_outcome,
        event.player_name as player_name,
        event.pass_recipient_name as recipient_name,
        event.minute as minute,
        event.second as second,
        event.pass_length as pass_length,
        event.pass_angle as pass_angle,
        event.location_x as location_x,
        event.location_y as location_y,
        event.end_location_x as end_location_x,
        event.end_location_y as end_location_y
    """
    
    try:
        results = db.query(
            query,
            {"event_id": event_id}
        )
        
        if not results:
            return ToolResult(
                success=False, 
                error=f"No context/possession data found for event {event_id}. Event may not exist or may not be part of a possession chain."
            )
        
        # Group passes in the buildup
        passes = []
        event_info = None
        
        for r in results:
            if not event_info:
                event_info = {
                    "event_type": r["event_type"],
                    "event_minute": r["event_minute"],
                    "event_period": r["event_period"],
                    "event_outcome": r["event_outcome"],
                }
            
            if r["player_name"]:
                passes.append({
                    "from": r["player_name"],
                    "to": r["recipient_name"],
                    "minute": r["minute"],
                    "second": r["second"],
                    "length": r["pass_length"],
                    "angle": r["pass_angle"],
                    "start_location": (r["location_x"], r["location_y"]) if r["location_x"] else None,
                    "end_location": (r["end_location_x"], r["end_location_y"]) if r["end_location_x"] else None,
                })
        
        # Build readable chain narrative
        chain_parts = []
        for p in passes:
            if p["to"]:
                chain_parts.append(f"{p['from']} → {p['to']}")
            else:
                chain_parts.append(f"{p['from']} (incomplete)")
        
        chain_narrative = " → ".join(chain_parts) if chain_parts else "No passes in possession"
        
        return ToolResult(
            success=True,
            data={
                "event": event_info,
                "buildup_chain": chain_narrative,
                "buildup_passes": passes,
                "total_passes": len(passes),
            },
            raw_query=query
        )
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_event_summary(
    db: Neo4jClient,
    event_id: str,
) -> ToolResult:
    """Get key moments leading to an event - concise summary for quick understanding.
    
    Parameters:
    - event_id: event ID from find_events() or find_goals()
    
    Returns: 3-5 key passes only (filters incomplete passes) with minimal details (players, distance, time).
    Use for: quick answers, post-game summaries, understanding main sequences without deep analysis.
    """
    query = """
    MATCH (target_event:Event {id: $event_id})
    MATCH (pos:Possession)-[:CONTAINS]->(target_event)
    MATCH (pos)-[:CONTAINS]->(event:Event)
    WHERE event.type = 'Pass'
    WITH target_event, event
    ORDER BY event.minute ASC, event.second ASC
    RETURN 
        target_event.type as event_type,
        target_event.minute as event_minute,
        target_event.period as event_period,
        COALESCE(target_event.shot_outcome, target_event.pass_outcome, target_event.duel_outcome) as event_outcome,
        event.player_name as player_name,
        event.pass_recipient_name as recipient_name,
        event.minute as minute,
        event.second as second,
        event.pass_length as pass_length
    """
    
    try:
        results = db.query(query, {"event_id": event_id})
        
        if not results:
            return ToolResult(
                success=False,
                error=f"No context found for event {event_id}"
            )
        
        # Extract event info
        event_info = {
            "event_type": results[0]["event_type"],
            "event_minute": results[0]["event_minute"],
            "event_period": results[0]["event_period"],
            "event_outcome": results[0]["event_outcome"],
        }
        
        # Filter complete passes (with recipient), take last 5
        complete_passes = [
            {
                "from": r["player_name"],
                "to": r["recipient_name"],
                "time": f"{r['minute']}:{r['second']:02d}",
                "distance_m": round(r["pass_length"], 1) if r["pass_length"] else None,
            }
            for r in results
            if r["player_name"] and r["recipient_name"]
        ]
        
        # Keep last 5 key passes (most relevant to the event)
        key_passes = complete_passes[-5:] if len(complete_passes) > 5 else complete_passes
        
        # Build chain narrative
        chain_parts = [f"{p['from']} → {p['to']}" for p in key_passes]
        chain_narrative = " → ".join(chain_parts) if chain_parts else "No complete passes"
        
        return ToolResult(
            success=True,
            data={
                "event": event_info,
                "key_sequence": chain_narrative,
                "key_passes": key_passes,
                "pass_count": len(key_passes),
            },
            raw_query=query
        )
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)

def get_player_actions(
    db: Neo4jClient,
    event_type: Optional[str] = None,
    team: Optional[str] = None,
    player: Optional[str] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
    limit: int = 10,
) -> ToolResult:
    """Get player actions by event type, time window, team, or player.\n    \n    Parameters:\n    - event_type: Pressure, Tackle, Interception, Duel, Ball Recovery, etc.\n    - team: team name\n    - player: player name\n    - minute_min/minute_max: time window\n    - limit: max results\n    \n    Examples: get_player_actions(event_type=\"Tackle\", team=\"Real Madrid\") or get_player_actions(event_type=\"Pressure\", minute_min=0, minute_max=20)\n    """
    params = {}
    
    # All events are :Event nodes with type property
    match_clause = "MATCH (event:Event)"
    where_conditions = []
    
    # Add type condition
    if event_type:
        where_conditions.append(f"event.type = '{event_type}'")
    else:
        # If no event type specified, match common action types
        where_conditions.append("event.type IN ['Pressure', 'Tackle', 'Interception', 'Duel', 'Ball Recovery']")
    
    # Time window filtering
    if minute_min is not None:
        where_conditions.append(f"event.minute >= {minute_min}")
    if minute_max is not None:
        where_conditions.append(f"event.minute <= {minute_max}")
    
    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)
    
    # Player/team filtering using flattened properties
    if player:
        params["player"] = player.lower()
        if where_clause:
            where_clause += f"\nAND LOWER(event.player_name) CONTAINS $player"
        else:
            where_clause = f"WHERE LOWER(event.player_name) CONTAINS $player"
    
    if team:
        params["team"] = team.lower()
        if where_clause:
            where_clause += f"\nAND LOWER(event.team_name) CONTAINS $team"
        else:
            where_clause = f"WHERE LOWER(event.team_name) CONTAINS $team"
    
    query = f"""{match_clause}
{where_clause}
WITH event.team_name as team, event.player_name as player, COUNT(event) as action_count
RETURN team, player, action_count
ORDER BY action_count DESC
LIMIT {limit}"""
    
    try:
        results = db.query(query, params)
        
        if not results:
            error_msg = f"No {event_type or 'action'} events found"
            if minute_min or minute_max:
                error_msg += f" in minute range {minute_min or 0}-{minute_max or 90}"
            return ToolResult(success=False, error=error_msg)
        
        actions_data = [
            {
                "team": r["team"],
                "player": r["player"],
                "action_count": r["action_count"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=actions_data, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_passing_pairs(
    db: Neo4jClient,
    team: Optional[str] = None,
    player: Optional[str] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
    limit: int = 10,
) -> ToolResult:
    """Get passing partnerships: passer-recipient pairs and pass counts.
    
    Parameters: team, player (passer), minute_min, minute_max, limit.
    Does NOT have event_type parameter - only returns Pass events.
    
    Examples: get_passing_pairs(team="Real Madrid") or get_passing_pairs(player="Benzema", minute_min=45, minute_max=90)
    """
    where_conditions = []
    params = {}
    
    match_clause = "MATCH (pass:Event)"
    where_conditions.append("pass.type = 'Pass'")
    
    # Time window filtering
    if minute_min is not None:
        where_conditions.append(f"pass.minute >= {minute_min}")
    if minute_max is not None:
        where_conditions.append(f"pass.minute <= {minute_max}")
    
    # Player filtering (using flattened player_name and pass_recipient_name)
    if player:
        params["player"] = player.lower()
        where_conditions.append("LOWER(pass.player_name) CONTAINS $player")
    
    # Team filtering (using flattened team_name)
    if team:
        params["team"] = team.lower()
        where_conditions.append("LOWER(pass.team_name) CONTAINS $team")
    
    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)
    
    query = f"""{match_clause}
{where_clause}
WITH pass.player_name as passer, pass.pass_recipient_name as recipient, COUNT(pass) as pass_count
RETURN passer, recipient, pass_count
ORDER BY pass_count DESC
LIMIT {limit}"""
    
    try:
        results = db.query(query, params)
        
        if not results:
            return ToolResult(success=False, error="No passing partnerships found")
        
        passing_data = [
            {
                "passer": r["passer"],
                "recipient": r["recipient"],
                "passes": r["pass_count"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=passing_data, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_team_stats(
    db: Neo4jClient,
    metric: str = "all",
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
) -> ToolResult:
    """Get aggregated team statistics: possession, pass completion, shots, etc.
    
    Use for: comparing teams, understanding overall match balance.
    Returns high-level stats for all teams (or filtered to a time window).
    
    Parameters:
    - metric: "all", "possession", "passes", "shots", "tackles"  (default: "all")
    - minute_min: start of time window  (optional)
    - minute_max: end of time window (optional)
    
    Returns:
    - Team-level aggregates: team name, metric value, counts
    
    Example queries:
    "Possession stats" → get_team_stats(metric="possession")
    "Who took more shots in first half?" → get_team_stats(metric="shots", minute_min=0, minute_max=45)
    "Overall match statistics" → get_team_stats()
    """
    time_filter = ""
    params = {}
    
    # Time window filtering
    if minute_min is not None or minute_max is not None:
        conditions = []
        if minute_min is not None:
            conditions.append(f"event.minute >= {minute_min}")
        if minute_max is not None:
            conditions.append(f"event.minute <= {minute_max}")
        time_filter = " AND ".join(conditions)
        if time_filter:
            time_filter = f"WHERE {time_filter}\n"
    
    # Build metric-specific queries
    if metric == "possession" or metric == "all":
        pass_query = f"""
        MATCH (pass:Event)
        WHERE pass.type = 'Pass'
        {time_filter}
        WITH pass.team_name as team, COUNT(pass) as pass_count
        RETURN team, 'pass_count' as metric, pass_count as value
        ORDER BY pass_count DESC
        """
    elif metric == "shots":
        pass_query = f"""
        MATCH (shot:Event)
        WHERE shot.type = 'Shot'
        {time_filter}
        WITH shot.team_name as team, COUNT(shot) as shot_count
        RETURN team, 'shots' as metric, shot_count as value
        ORDER BY shot_count DESC
        """
    elif metric == "tackles":
        pass_query = f"""
        MATCH (tackle:Event)
        WHERE tackle.type = 'Tackle'
        {time_filter}
        WITH tackle.team_name as team, COUNT(tackle) as tackle_count
        RETURN team, 'tackles' as metric, tackle_count as value
        ORDER BY tackle_count DESC
        """
    else:
        pass_query = f"""
        MATCH (pass:Event)
        WHERE pass.type = 'Pass'
        {time_filter}
        WITH pass.team_name as team, COUNT(pass) as pass_count
        RETURN team, 'pass_count' as metric, pass_count as value
        ORDER BY pass_count DESC
        """
    
    try:
        results = db.query(pass_query, params)
        
        if not results:
            return ToolResult(success=False, error=f"No {metric} statistics found")
        
        stats_data = [
            {
                "team": r["team"],
                "metric": r["metric"],
                "value": r["value"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=stats_data, raw_query=pass_query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=pass_query)


def get_team_formation(
    db: Neo4jClient,
    team_id: str,
    minute: int,
) -> ToolResult:
    """Get the formation a team was using at a specific moment.
    
    Use this tool when:
    - User asks about tactical setup, formation, organization
    - You need to understand defensive structure at key moments
    - You want to explain how a team lined up
    - User asks "what formation were they in?"
    
    Returns:
    - team: Team name
    - formation: Formation string (e.g., "4-3-3", "5-2-3") if available
    - minute: Timestamp of the formation data
    
    Note: Formation data may be limited in the match dataset.
    
    Example questions this answers:
    "What was the formation during the goal?"
    "How was the team organized in the second half?"
    """
    # Starting XI events contain formation info
    query = """
    MATCH (m:Match)
    MATCH (m)<-[:IN_MATCH]-(t:Team {id: $team_id})
    OPTIONAL MATCH (xi:Event {type: "Starting XI", team_id: $team_id})-[:IN_MATCH]->(m)
    RETURN t.name as team_name, xi.play_pattern as formation
    LIMIT 1
    """
    
    try:
        results = db.query(
            query,
            {"team_id": team_id}
        )
        
        if not results:
            return ToolResult(success=False, error="Formation not found for this team")
        
        return ToolResult(
            success=True,
            data={
                "team": results[0]["team_name"],
                "formation": results[0]["formation"] or "Not recorded",
                "minute": minute,
            },
            raw_query=query
        )
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_pressing_intensity(
    db: Neo4jClient,
    period: Optional[int] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
    team: Optional[str] = None,
    limit: int = 10,
) -> ToolResult:
    """Analyze pressing events. DEPRECATED - use get_player_actions(event_type="Pressure") instead.
    
    For backward compatibility, converts period to minute ranges:
    - period 1 = minute_min=0, minute_max=45
    - period 2 = minute_min=45, minute_max=90
    
    But it's better to use: get_player_actions(event_type="Pressure", minute_min=X, minute_max=Y)
    """
    # Convert period to minute ranges for backward compatibility
    if period == 1:
        minute_min, minute_max = 0, 45
    elif period == 2:
        minute_min, minute_max = 45, 90
    
    return get_player_actions(
        db,
        event_type="Pressure",
        team=team,
        minute_min=minute_min,
        minute_max=minute_max,
        limit=limit
    )


def get_possession_stats(
    db: Neo4jClient,
    period: Optional[int] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
) -> ToolResult:
    """Get team possession statistics. DEPRECATED - use get_team_stats(metric="possession", minute_min=X, minute_max=Y) instead.
    
    For backward compatibility, converts period to minute ranges:
    - period 1 = minute_min=0, minute_max=45
    - period 2 = minute_min=45, minute_max=90
    
    Better to use: get_team_stats(metric="possession", minute_min=0, minute_max=45)
    """
    # Convert period to minute ranges for backward compatibility
    if period == 1:
        minute_min, minute_max = 0, 45
    elif period == 2:
        minute_min, minute_max = 45, 90
    
    return get_team_stats(db, metric="possession", minute_min=minute_min, minute_max=minute_max)


def get_attacking_patterns(
    db: Neo4jClient,
    period: Optional[int] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
) -> ToolResult:
    """Analyze shots. DEPRECATED - use find_events(event_type='Shot', minute_min=X, minute_max=Y) instead.
    Backward compatible: period 1 = 0-45 minutes, period 2 = 45-90 minutes."""
    if period == 1:
        minute_min, minute_max = 0, 45
    elif period == 2:
        minute_min, minute_max = 45, 90
    return find_events(db, event_type="Shot", minute_min=minute_min, minute_max=minute_max)


def analyze_transitions(
    db: Neo4jClient,
    period: Optional[int] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
) -> ToolResult:
    """Analyze transitions. DEPRECATED - use get_player_actions(event_type='BallRecovery', minute_min=X) instead.
    Backward compatible: period 1 = 0-45 minutes, period 2 = 45-90 minutes."""
    if period == 1:
        minute_min, minute_max = 0, 45
    elif period == 2:
        minute_min, minute_max = 45, 90
    return get_player_actions(db, event_type="BallRecovery", minute_min=minute_min, minute_max=minute_max)


def get_pass_network(
    db: Neo4jClient,
    team: Optional[str] = None,
    period: Optional[int] = None,
) -> ToolResult:
    """Analyze passing partnerships. DEPRECATED - use get_passing_pairs(team=X, minute_min=Y) instead.
    Backward compatible: period 1 = 0-45 minutes, period 2 = 45-90 minutes."""
    minute_min, minute_max = None, None
    if period == 1:
        minute_min, minute_max = 0, 45
    elif period == 2:
        minute_min, minute_max = 45, 90
    return get_passing_pairs(db, team=team, minute_min=minute_min, minute_max=minute_max)


def analyze_defensive_organization(
    db: Neo4jClient,
    period: Optional[int] = None,
    minute_min: Optional[int] = None,
    minute_max: Optional[int] = None,
) -> ToolResult:
    """Analyze defensive actions. DEPRECATED - use get_player_actions(event_type='Tackle', minute_min=X) instead.
    Backward compatible: period 1 = 0-45 minutes, period 2 = 45-90 minutes."""
    if period == 1:
        minute_min, minute_max = 0, 45
    elif period == 2:
        minute_min, minute_max = 45, 90
    return get_player_actions(db, event_type="Tackle", minute_min=minute_min, minute_max=minute_max)


def get_match_players(
    db: Neo4jClient,
    team: Optional[str] = None,
) -> ToolResult:
    """Get list of all players in the match, optionally filtered by team.
    
    Use this tool when:
    - User asks "who played?" or "show me all players"
    - You need to verify exact player names before using other tools
    - A player name query returned no results and you want to see available options
    - Confirming correct spelling of a player name
    
    Parameters:
    - team: optional team name filter (e.g., "Real Madrid") - if omitted, returns all players
    
    Returns:
    - List of all players: player name, team, shirt number
    - Sorted by team then by player name
    - Use this to find exact spellings if fuzzy matching didn't find what you wanted
    
    Example queries:
    "Get all players" → get_match_players()
    "Show Real Madrid's squad" → get_match_players(team="Real Madrid")
    "Who are the attacking players?" → Call this first to see names, then ask more specific questions
    """
    where_clause = ""
    params = {}
    
    if team:
        params["team"] = team.lower()
        where_clause = "WHERE LOWER(t.name) CONTAINS $team"
    
    query = f"""MATCH (p:Player)-[:PLAYS_FOR]->(t:Team)
{where_clause}
RETURN 
    p.name as player_name,
    t.name as team,
    p.shirt_number as shirt_number
ORDER BY t.name ASC, p.name ASC"""
    
    try:
        results = db.query(query, params)
        
        if not results:
            team_filter = f" for {team}" if team else ""
            return ToolResult(success=False, error=f"No players found{team_filter}")
        
        players = [
            {
                "player": r["player_name"],
                "team": r["team"],
                "shirt_number": r["shirt_number"] or "N/A",
            }
            for r in results
        ]
        
        return ToolResult(
            success=True,
            data=players,
            raw_query=query
        )
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def list_available_tools() -> list[dict]:
    """Dynamically extract tool metadata from function docstrings.
    
    Works like MCP: reads the docstring from each tool function to provide
    comprehensive documentation to the agent without maintaining a separate list.
    
    Returns a list of dicts with:
    - name: Function name
    - docstring: Full docstring (explains usage, parameters, examples)
    """
    # Get all functions in this module that are tools (not starting with _)
    tools_module = inspect.getmodule(list_available_tools)
    tool_functions = [
        name for name in dir(tools_module)
        if not name.startswith('_')
        and callable(getattr(tools_module, name))
        and name not in ['list_available_tools', 'ToolResult', 'PossessionChain', 'PassData', 'FormationSnapshot', 'Optional', 'Any', 'inspect', 'Neo4jClient']
    ]
    
    tools_list = []
    for tool_name in tool_functions:
        func = getattr(tools_module, tool_name)
        sig = inspect.signature(func)
        
        # Extract parameter names (skip db_client parameter)
        params = [p for p in sig.parameters.keys() if p != 'db']
        
        tools_list.append({
            "name": tool_name,
            "docstring": inspect.getdoc(func) or "No documentation available",
            "parameters": params,
        })
    
    return sorted(tools_list, key=lambda x: x["name"])