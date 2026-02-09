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


def find_goals(db: Neo4jClient) -> ToolResult:
    """Find all goals scored in the current match.
    
    Use this tool when:
    - User asks about goals, scorers, goal timing
    - You need to identify key moments to analyze
    - You want to find turning points in the match
    
    Returns:
    - minute: When the goal was scored (match minute)
    - period: Which period (1 or 2)
    - scorer: Player name who scored
    - team: Team name of the scorer
    
    Example questions this answers:
    "When was the first goal?"
    "Who scored?"
    "Explain the buildup to the goal at minute 45"
    """
    query = """
    MATCH (e:Shot {outcome: "Goal"})
    MATCH (e)-[:BY]->(p:Player)
    MATCH (p)-[:PLAYS_FOR]->(t:Team)
    RETURN e.id as event_id, e.minute as minute, e.period as period, p.name as scorer, t.name as team
    ORDER BY e.minute ASC
    """
    
    try:
        results = db.query(query)
        goals = [
            {
                "minute": r["minute"],
                "period": r["period"],
                "scorer": r["scorer"],
                "team": r["team"],
            }
            for r in results
        ]
        
        return ToolResult(
            success=True,
            data=goals,
            raw_query=query,
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_possession_before_event(
    db: Neo4jClient,
    event_id: str,
) -> ToolResult:
    """Retrieve the possession chain that led to a specific event.
    
    Use this tool when:
    - User asks about buildup play leading to a shot/goal
    - You want to understand how a team progressed the ball
    - You need to analyze tactical patterns in a possession
    - User asks "explain the play before..." or "how did they score?"
    
    Returns:
    - A list of passes with player names (passer → recipient)
    - Pass count and sequence
    - Status: whether data was found
    
    Example questions this answers:
    "Analyze the buildup to the goal"
    "What was the passing pattern before they scored?"
    "How did the team progress from defense to attack?"
    """
    query = """
    MATCH (e:Event {id: $event_id})
    MATCH (pos:Possession)-[:CONTAINS]->(e)
    MATCH (pos)-[:CONTAINS]->(pass_event:Pass)
    MATCH (pass_event)-[:BY]->(passer:Player)
    OPTIONAL MATCH (pass_event)-[:TO_PLAYER]->(recipient:Player)
    RETURN 
        passer.name as player_name,
        recipient.name as recipient_name,
        pass_event.minute as minute
    ORDER BY pass_event.minute ASC
    """
    
    try:
        results = db.query(
            query,
            {"event_id": event_id}
        )
        
        if not results:
            return ToolResult(success=False, error="No possession chain found for this event")
        
        passes = [
            {
                "from": r["player_name"],
                "to": r["recipient_name"],
                "minute": r["minute"],
            }
            for r in results
        ]
        
        return ToolResult(
            success=True,
            data={
                "passes": passes,
                "total_passes": len(passes),
            },
            raw_query=query
        )
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


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
    OPTIONAL MATCH (xi:Event {type: "Starting XI"})-[:IN_MATCH]->(m)
    WHERE xi.team_id = $team_id
    RETURN t.name as team_name, xi.formation as formation
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
    period: int,
    team_id: Optional[str] = None,
) -> ToolResult:
    """Analyze pressing events by team and player during a period.
    
    Use this tool when:
    - User asks about defensive intensity, pressing, aggression in a specific half
    - Want to understand which team pressed more
    - Analyzing defensive strategies
    
    Parameters:
    - period: REQUIRED (1 or 2) - which half to analyze
    - team_id: optional - filter to one team's perspective
    
    Returns:
    - Subgraph: Pressure events per team, limited to top 10 most active pressers
    - For each: player name, team name, pressure count
    - Includes only players with 2+ pressure events (removes noise)
    
    Example questions this answers:
    "How aggressive was the defense in the first half?"
    "Which team pressed more in period 2?"
    """
    team_filter = f"AND t.id = '{team_id}'" if team_id else ""
    
    query = f"""
    MATCH (pressure:Pressure {{period: $period}})
    MATCH (pressure)-[:BY]->(p:Player)
    MATCH (p)-[:PLAYS_FOR]->(t:Team)
    WITH t.name as team, p.name as player, COUNT(pressure) as count
    WHERE count >= 2  -- Remove singleton events
    RETURN team, player, count
    ORDER BY team, count DESC
    LIMIT 10
    """
    
    try:
        results = db.query(query, {"period": period})
        
        if not results:
            return ToolResult(success=False, error="No significant pressure events found in this period")
        
        pressure_data = [
            {
                "team": r["team"],
                "player": r["player"],
                "pressure_events": r["count"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=pressure_data, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_possession_stats(
    db: Neo4jClient,
    period: Optional[int] = None,
) -> ToolResult:
    """Get raw pass counts by team (subgraph data).
    
    Use this tool when:
    - User asks about possession or ball control
    - You need to understand which team played more passes
    - Analyzing possession patterns in first vs second half
    
    Returns:
    - Subgraph: Complete pass counts for each team
    - Includes: team name and total passes
    - Agent can compute percentages from raw counts
    
    Example questions this answers:
    "Who had more possession?"
    "Did possession change in the second half?"
    "Which team controlled the ball more?"
    """
    if period:
        period_filter = f"WHERE e.period = {period}"
    else:
        period_filter = ""
    
    query = f"""
    MATCH (e:Pass)
    {period_filter}
    MATCH (e)-[:BY]->(p:Player)
    MATCH (p)-[:PLAYS_FOR]->(t:Team)
    WITH t.name as team_name, COUNT(e) as pass_count
    RETURN team_name, pass_count
    ORDER BY team_name
    """
    
    try:
        results = db.query(query)
        
        if not results:
            return ToolResult(success=False, error="No pass data found")
        
        possession_data = [
            {
                "team": r["team_name"],
                "passes": r["pass_count"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=possession_data, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_attacking_patterns(
    db: Neo4jClient,
    period: Optional[int] = None,
) -> ToolResult:
    """Analyze shots and scoring by team (aggregated).
    
    Use this tool when:
    - User asks about attacking strategies, shots, goals, efficiency
    - Understanding offensive output and shooting
    - Comparing attacking performance between periods
    
    Parameters:
    - period: optional (1 or 2) - restrict to one half. If not provided, analyzes entire match.
    
    Returns:
    - Subgraph: Aggregated shot stats per team
    - Includes: team, total shots, goals, and list of goal scorers with minutes
    
    Example questions this answers:
    "How many shots did they have?"
    "Who scored?"
    "How efficient was their finishing?"
    """
    period_filter = f"WHERE shot.period = {period}" if period else ""
    
    query = f"""
    MATCH (shot:Shot)
    {period_filter}
    MATCH (shot)-[:BY]->(p:Player)
    MATCH (p)-[:PLAYS_FOR]->(t:Team)
    WITH 
        t.name as team,
        COUNT(shot) as total_shots,
        COUNT(CASE WHEN shot.outcome = 'Goal' THEN 1 END) as goals,
        COLLECT(CASE WHEN shot.outcome = 'Goal' THEN p.name + ' (' + shot.minute + ')' END) as scorers
    RETURN team, total_shots, goals, [s IN scorers WHERE s IS NOT NULL] as goal_list
    ORDER BY team
    """
    
    try:
        results = db.query(query)
        
        if not results:
            return ToolResult(success=False, error="No shot data found")
        
        shots_data = [
            {
                "team": r["team"],
                "shots": r["total_shots"],
                "goals": r["goals"],
                "scorers": r["goal_list"] if r["goal_list"] else [],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=shots_data, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def analyze_transitions(
    db: Neo4jClient,
    period: Optional[int] = None,
) -> ToolResult:
    """Analyze ball recovery events (transitions) by team.
    
    Use this tool when:
    - User asks about transition play, counter-attacks, tempo
    - Understanding how teams switch from defense to attack
    - Want to know which team transitions more
    
    Parameters:
    - period: optional (1 or 2) - restrict to one half. If not provided, analyzes both.
    
    Returns:
    - Subgraph: Top 5 most-involved players in transitions per team
    - Includes: team, player, recovery count
    - Ranked by number of recovery events
    
    Example questions this answers:
    "How good were they on the counter?"
    "Which team transitioned faster/more?"
    "Who won the ball most often?"
    """
    period_filter = f"AND recovery.period = {period}" if period else ""
    
    query = f"""
    MATCH (recovery:Interception|BallRecovery)
    {period_filter}
    MATCH (recovery)-[:BY]->(p:Player)
    MATCH (p)-[:PLAYS_FOR]->(t:Team)
    WITH t.name as team, p.name as player, COUNT(recovery) as count
    RETURN team, player, count
    ORDER BY team, count DESC
    LIMIT 10
    """
    
    try:
        results = db.query(query)
        
        if not results:
            return ToolResult(success=False, error="No recovery events found")
        
        transition_data = [
            {
                "team": r["team"],
                "player": r["player"],
                "recoveries": r["count"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=transition_data, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def get_pass_network(
    db: Neo4jClient,
    team_id: Optional[str] = None,
) -> ToolResult:
    """Analyze passing partnerships between players (top connections).
    
    Use this tool when:
    - User asks about who passed to whom most, key partnerships
    - Understanding playmaking chains and connections
    - Identifying dominant passing relationships
    
    Parameters:
    - team_id: optional - filter to one team's passing network. If not provided, shows all teams' top partnerships.
    
    Returns:
    - Subgraph: Top 10 passing partnerships (passer → recipient)
    - Includes: from_player, to_player, team, pass count
    - Ranked by frequency
    
    Example questions this answers:
    "Who were the key passers?"
    "Which players connected the most?"
    "What was the passing structure?"
    """
    team_filter = f"WHERE t.id = '{team_id}'" if team_id else ""
    
    query = f"""
    MATCH (pass:Pass)-[:BY]->(p1:Player)-[:PLAYS_FOR]->(t:Team)
    MATCH (pass)-[:TO_PLAYER]->(p2:Player)
    {team_filter}
    WITH 
        p1.name as passer,
        p2.name as recipient,
        t.name as team,
        COUNT(pass) as passes
    RETURN passer, recipient, team, passes
    ORDER BY passes DESC
    LIMIT 10
    """
    
    try:
        results = db.query(query)
        
        if not results:
            return ToolResult(success=False, error="No passing data found")
        
        partnerships = [
            {
                "from": r["passer"],
                "to": r["recipient"],
                "team": r["team"],
                "passes": r["passes"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=partnerships, raw_query=query)
    
    except Exception as e:
        return ToolResult(success=False, error=str(e), raw_query=query)


def analyze_defensive_organization(
    db: Neo4jClient,
    period: Optional[int] = None,
) -> ToolResult:
    """Analyze which players were most active defensively.
    
    Use this tool when:
    - User asks about defensive organization, structure, or key defenders
    - Want to know who made the most tackles/interceptions
    - Comparing defensive activity between periods
    
    Parameters:
    - period: optional (1 or 2) - restrict to one half. If not provided, analyzes both.
    
    Returns:
    - Subgraph: Top 10 most-active defenders per team (aggregated)
    - Includes: team, player, count of their defensive actions (tackles/duels/interceptions)
    - Ranked by defensive action count
    
    Example questions this answers:
    "Who was the best defender?"
    "How did the defense organize?"
    "Who made key defensive plays?"
    """
    period_filter = f"AND event.period = {period}" if period else ""
    
    query = f"""
    MATCH (event:Tackle|Duel|Interception)
    {period_filter}
    MATCH (event)-[:BY]->(p:Player)
    MATCH (p)-[:PLAYS_FOR]->(t:Team)
    WITH t.name as team, p.name as player, COUNT(event) as action_count
    RETURN team, player, action_count
    ORDER BY team, action_count DESC
    LIMIT 10
    """
    
    try:
        results = db.query(query)
        
        if not results:
            return ToolResult(success=False, error="No defensive events found")
        
        defensive_data = [
            {
                "team": r["team"],
                "player": r["player"],
                "defensive_actions": r["action_count"],
            }
            for r in results
        ]
        
        return ToolResult(success=True, data=defensive_data, raw_query=query)
    
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
