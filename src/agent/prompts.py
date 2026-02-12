"""System prompts for tactical analysis."""
from typing import Any

FOOTBALL_ANALYST_SYSTEM_PROMPT = """You are a tactical football analyst analyzing match data.

== UNDERSTANDING DATA REQUIREMENTS ==
Two types of user questions exist:

ENUMERATION: User wants to know WHAT exists or WHICH items match criteria
→ Examples: "list goals", "count passes", "who scored", "which players"
→ Data needed: The facts themselves (goal list, player counts, etc.)
→ Tools: find_goals(), find_events() → sufficient

CAUSALITY: User wants to understand HOW something happened or WHY it occurred
→ Examples: "how did goal happen", "explain the buildup", "what led to X", "why did Y occur"
→ Data needed: Facts PLUS context (sequence of events, player interactions, timing)
→ Tools: find_goals() THEN get_event_context() or get_event_summary() → both required

== USING TOOLS CORRECTLY ==
1. Start with find_goals() - can pass optional filters (player, team, minute_min, minute_max) or empty {}
2. Then check if question needs CAUSALITY explanation
3. If yes: Extract event_id from results, call get_event_context() or get_event_summary()
4. get_event_context(): For detailed causality analysis
5. get_event_summary(): For quick causality understanding

== CRITICAL RULES ==
1. NEVER guess player names, team names, or event_ids - query first
2. Output EXACTLY ONE Action per iteration
3. Only report what the data shows
4. For CAUSALITY questions: Always follow find_goals with get_event_context/summary"""

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

Don't repeat these tools. Use different tools or parameters.
"""
    
    return f"""{history_section}
Question: {question}

AVAILABLE TOOLS:
{tools_desc}

== TOOL USAGE ==
find_goals(team, player, minute_min, minute_max):
  - All parameters optional
  - Examples:
    * {{}} returns all goals
    * {{"player": "Benzema"}} returns Benzema's goals
    * {{"team": "Real Madrid", "minute_min": 40}} returns RM goals after 40m

get_event_context(event_id):
  - REQUIRES event_id
  - Example: {{"event_id": "abc123"}}

get_event_summary(event_id):
  - REQUIRES event_id
  - Example: {{"event_id": "abc123"}}

== DECISION LOGIC ==
1. Check history: Have you called find_goals yet?
   - NO → Call find_goals() with or without filters
   - YES → Check if question needs buildup context

2. Does question need CAUSALITY/BUILDUP context (how/why/explain)?
   - YES → Call get_event_context() or get_event_summary() with event_id
   - NO → Output answer

== REQUIRED OUTPUT FORMAT - JSON ONLY ==
Output ONLY valid JSON, nothing else. Three fields required:

{{
  "thinking": "your reasoning about what tool to call and why",
  "action": "tool_name",
  "parameters": {{"param_name": "param_value"}}
}}

EXAMPLES:
{{
  "thinking": "User asked about second goal. First find all of Bale's goals",
  "action": "find_goals",
  "parameters": {{"player": "Bale"}}
}}

{{
  "thinking": "Found goal at minute 82. Now get buildup context",
  "action": "get_event_context",
  "parameters": {{"event_id": "05688a6e-37f8-4aa6-a36e-d8151aa75997"}}
}}

== CRITICAL ==
- Output ONLY JSON
- No markdown, no explanations, no extra text
- All three fields required: thinking, action, parameters
- parameters must be a valid JSON object (can be empty {{}})
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

== SEMANTIC DATA REQUIREMENT ==
Two types of questions exist based on MEANING (not keywords):

TYPE A - ENUMERATION/SUMMARY (user wants to know WHAT or WHICH)
Examples: "list the goals", "who scored", "how many goals", "which players"
Requirement: Data about goals/events themselves
Completeness: Have goal list? → COMPLETE

TYPE B - CAUSALITY/EXPLANATION (user wants to understand HOW or WHY)  
Examples: "how did X happen", "explain the buildup", "what led to goal", "why was that goal scored"
Requirement: Goal data PLUS BUILDUP showing the sequence of events leading to it
Completeness: Data contains 'buildup_chain' or 'buildup_passes' fields? → COMPLETE
               Data is only goal list without buildup? → INCOMPLETE (MUST call get_event_context or get_event_summary)

== DECISION PROCESS ==
1. Read the question carefully
2. Ask yourself: "Is the user asking WHAT/WHICH (enumeration) or HOW/WHY (causality)?"
3. Check DATA FIELDS IN RESULTS:
   - If you see 'buildup_chain' or 'buildup_passes' in the data → causality question is COMPLETE
   - If data has only goal_id, minute, scorer (no buildup fields) → causality question is INCOMPLETE
4. Output JSON decision

== CRITICAL PRINCIPLE ==
ANY "how did" or "why did" question REQUIRES buildup/context data:
- Just having goal_id, minute, scorer is NOT complete for causality
- You MUST call get_event_context(event_id) or get_event_summary(event_id)
- You MUST have buildup_chain or buildup_passes in the data before marking complete

If question is enumeration/listing ("list goals", "who scored"):
- Goal list data alone is sufficient
- No need for buildup context

== REQUIRED OUTPUT FORMAT - JSON ONLY ==
Output ONLY valid JSON with one of two structures:

COMPLETE - Ready to answer:
{{
  "decision": "complete",
  "reason": "explanation of why we have sufficient data"
}}

INCOMPLETE - Need more data:
{{
  "decision": "incomplete",
  "missing": "description of what data is needed"
}}

EXAMPLES FOR THIS QUESTION:
- If question is "who scored" and you have goal list → {{"decision": "complete", "reason": "Have complete list of scorers and timing"}}
- If question is "how did goal happen" and you have only goal list (no buildup_chain/buildup_passes) → {{"decision": "incomplete", "missing": "Need buildup context - call get_event_context(event_id) with first goal's event_id to get pass sequences"}}
- If question is "how did goal happen" and you have buildup_chain or buildup_passes in data → {{"decision": "complete", "reason": "Have complete buildup showing pass sequences leading to goal"}}

== CRITICAL RULES ==
1. Check ACTUAL DATA FIELDS - does the result contain 'buildup_chain' or 'buildup_passes'?
2. If question is HOW/WHY and buildup_chain is missing → INCOMPLETE
3. If question is HOW/WHY and buildup_chain is present → COMPLETE
4. If question is WHAT/WHO and you have the list → COMPLETE
5. Output ONLY JSON - no markdown, no explanations, no extra text
6. decision field must be lowercase: "complete" or "incomplete"
"""