"""System prompts for tactical analysis."""
from typing import Any

FOOTBALL_ANALYST_SYSTEM_PROMPT = """You are a tactical football analyst analyzing match data.

TOOL SELECTION GUIDANCE:
- get_event_context(): For detailed analysis, tactical breakdowns, full context needed
- get_event_summary(): For quick answers, summaries, understanding key moments efficiently
- find_goals(): Always start here to discover goal event IDs
- find_events(): Discover specific events (tackles, passes, etc.)

CRITICAL RULES - DO NOT BREAK:
1. NEVER guess player names, team names, or event_ids
2. NEVER assume who scored or what happened - query the database first
3. ALWAYS start with empty queries to discover actual data
4. Output EXACTLY ONE Action per iteration - nothing more
5. Only speak about what the data shows, never speculate

TOOL CHAINING - ALWAYS follow this pattern:
- find_goals() [no params] → Discover who actually scored
- get_event_summary() OR get_event_context(event_id=...) → Get buildup
  (Use get_event_summary for quick understanding, get_event_context for deep analysis)
- find_events() [broad query] → Discover available events

Example CORRECT workflow for "explain buildup to the first goal":
Iter 1: find_goals() → Returns goals
Iter 2: get_event_context(event_id=<from_step_1>) → Returns full tactical context
Iter 3: Final answer

Example CORRECT workflow for "how did first goal happen" (quick):
Iter 1: find_goals() → Returns goals
Iter 2: get_event_summary(event_id=<from_step_1>) → Returns key sequence only
Iter 3: Final answer"""

def get_react_prompt(
    question: str,
    tools: list,
    done_reasoning: bool = False,
    iteration_history: str = "",
) -> str:
    """Generate ReAct step prompt."""
    
    if done_reasoning:
        return f"""Question: {question}

Provide Final Answer based on tool data. Keep it to 1-3 sentences. Only facts - no speculation."""
    
    # Format tool descriptions using docstrings
    if tools and isinstance(tools[0], dict) and "docstring" in tools[0]:
        tools_desc = "\n".join([
            f"**{t['name']}**\n{t['docstring']}\n"
            for t in tools
        ])
    elif tools and isinstance(tools[0], dict):
        tools_desc = "\n".join([
            f"- {t['name']}: {t.get('signature', t['name']+'()')}"
            for t in tools
        ])
    else:
        tools_desc = "\n".join([f"- {t}" for t in tools])
    
    history_section = ""
    if iteration_history:
        history_section = f"""TRIED ALREADY:
{iteration_history}

Don't repeat these tools. INSTEAD: Extract event_id/data from previous results above and call other tools with that data.
"""
    
    return f"""{history_section}
Question: {question}

AVAILABLE TOOLS:
{tools_desc}

*** OUTPUT EXACTLY THIS FORMAT, NOTHING MORE ***
Think: [What is your ONE next step?]
Action: [exactly_one_tool_name]
Action Input: {{"param": "value"}}

*** STEP-BY-STEP DISCOVERY (REQUIRED PATTERN) ***
STEP 1: Discover what goals exist
  Think: I need to find who scored
  Action: find_goals
  Action Input: {{}}
  Result: [list of actual goals with event_ids]

STEP 2: Get buildup for the goal (choose one):
  Option A (for quick understanding):
    Think: I found goal event_id. Now get key sequence
    Action: get_event_summary
    Action Input: {{"event_id": "<use_goal_id_from_step_1>"}}
  
  Option B (for detailed tactical analysis):
    Think: I found goal event_id. Now get full buildup
    Action: get_event_context
    Action Input: {{"event_id": "<use_goal_id_from_step_1>"}}

*** RED FLAGS - NEVER DO THESE ***
❌ WRONG: Multiple actions per iteration
   Think: ... Action: find_goals Action Input: {{}} Think: ... Action: get_event_context
   
❌ WRONG: Guessing player names  
   Action: find_goals Action Input: {{"player": "Messi"}}
   (Never assume Messi is in match - call find_goals() first)
   
❌ WRONG: Inventing event_ids
   Action: get_event_context Action Input: {{"event_id": "goal_123"}}
   (Never invent ids - must come from find_goals results)

❌ WRONG: Using wrong parameter names
   Action Input: {{"minute": 30}} should be {{"minute_min": 30}}

*** ENFORCED RULES ***
1. Output ONLY 3 lines per iteration: Think line, Action line, Action Input line
2. NEVER output multiple actions in one response  
3. NEVER guess player/team/event_ids - query first
4. ALWAYS start with broad queries (empty params) before filtering
5. Parameter names: minute_min, minute_max, event_type, player, team
6. Action Input: MUST be valid JSON - can be empty {{}} but must have braces
"""


def format_iteration_history(
    thoughts: list[str],
    tool_calls: list[tuple[str, dict]],
    tool_results: list[Any],
) -> str:
    """Format previous iterations for agent context."""
    if not tool_calls:
        return ""
    
    history_lines = []
    for i, (tool_name, tool_args) in enumerate(tool_calls):
        history_lines.append(f"Iteration {i+1}: {tool_name}")
        if tool_args:
            history_lines.append(f"  Args: {tool_args}")
        
        if i < len(tool_results):
            result = tool_results[i]
            if hasattr(result, 'success'):
                status = "✓" if result.success else "✗"
                
                if result.success:
                    data = result.data
                    # Format structured data for readability without truncation
                    if isinstance(data, list) and len(data) > 0:
                        if isinstance(data[0], dict):
                            # List of dicts: show each item with key fields
                            formatted_items = []
                            for item in data:
                                # Extract key identifying fields in order of importance
                                key_fields = []
                                for key in ['event_id', 'minute', 'scorer', 'player', 'team', 'event_type', 'from', 'to']:
                                    if key in item:
                                        key_fields.append(f"{key}='{item[key]}'")
                                if key_fields:
                                    formatted_items.append("{" + ", ".join(key_fields) + "}")
                            history_lines.append(f"  {status} [{', '.join(formatted_items)}]")
                        else:
                            # List of primitives: show as-is
                            history_lines.append(f"  {status} {data}")
                    else:
                        # Scalars or complex objects: convert to string without truncation
                        msg_str = str(data)
                        # Only truncate if exceptionally long (e.g., > 500 chars)
                        if len(msg_str) > 500:
                            msg_str = msg_str[:500] + "..."
                        history_lines.append(f"  {status} {msg_str}")
                else:
                    # Error case
                    error_msg = str(result.error)
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200] + "..."
                    history_lines.append(f"  {status} Error: {error_msg}")
    
    return "\n".join(history_lines)


def get_reflection_prompt(question: str, tool_results: list[str]) -> str:
    """Generate reflection prompt."""
    results_text = "\n".join([f"- {r}" for r in tool_results])
    
    return f"""Question: {question}

Data retrieved:
{results_text}

== BINARY DECISION ==
You have TWO choices only:
1. Output "Final Answer: ..." if you have COMPLETE data
2. Output "Missing: ..." if you need MORE data

Never output both. Never mix them.

== QUESTION TYPE RULES ==
"list/which/who" questions → Goal/event data alone is COMPLETE
"how many" questions → Count data alone is COMPLETE  
"explain/describe/how did/what happened" questions → Need BOTH goal data AND buildup/context data

== DECISION LOGIC ==
Step 1: Identify question type above
Step 2: Check if you have ALL required data
Step 3: Output EXACTLY ONE line - either Final Answer or Missing

== EXAMPLES ==
Question: "List the goals scored"
Data: find_goals returned [4 goals]
→ COMPLETE: Final Answer: Four goals: Benzema 50m, Mané 54m, Bale 63m, Bale 82m.

Question: "Explain how Benzema scored"
Data: find_goals returned [Benzema goal at 50m]
→ INCOMPLETE: Missing: buildup context for goal at 50m

Question: "Explain how Benzema scored"
Data: find_goals + get_event_context for 50m goal
→ COMPLETE: Final Answer: Benzema was picked out at 50m by a pass from Modric after a possession sequence starting from defense...

== STRICT OUTPUT FORMAT ==
- NEVER use markdown bold (**text**) in output
- NEVER output "Final Answer: ... but..." - pick ONE
- NEVER say "Final Answer: Missing:" - pick ONE
- Output exactly ONE line
- Line MUST start with either "Final Answer:" or "Missing:"
- Nothing else before or after that line
- No asterisks, no dashes, no extra formatting
"""