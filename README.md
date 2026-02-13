# AI Tactico

**An AI Engineering exploration of agentic reasoning over knowledge graphs.**

Football tactical analysis agent powered by **LangGraph ReAct**, Neo4j knowledge graphs, and specialized tool design. The agent performs iterative reasoning (think→act→reflect→answer) to answer complex tactical questions about football matches using [StatsBomb](https://github.com/statsbomb/open-data) football event data.

## Core Architecture: LangGraph ReAct Agent

The heart of this project is a **ReAct (Reasoning + Acting) agent** orchestrated by LangGraph:

```
User Question
    ↓
[THINK] Agent reasons about question, identifies information needs
    ↓
[ACT] Agent selects appropriate tool(s) to retrieve data from Neo4j
    ↓
[REFLECT] Agent analyzes tool results, decides if more info is needed
    ├→ More needed? Loop back to THINK
    └→ Sufficient? Proceed to ANSWER
    ↓
[ANSWER] Agent synthesizes findings into tactical insight
    ↓
Response to User
```

## Key Components

**LangGraph Agent Graph** (`src/agent/agent.py`):
- 4-node directed graph: `_think_node` → `_act_node` → `_reflect_node` → `_answer_node`
- Conditional edges: `_act_node` validates tool parsing; `_reflect_node` decides loop continuation
- Early stopping: When agent produces "Final Answer:", loop terminates immediately
- Max iterations: Prevents infinite reasoning loops (currently 10)

**Tool System** (9 Specialized Queries)
- 9 Neo4j tools for football analysis (not general-purpose graph traversal)
- Compact helper tools (`get_last_touch`, `get_possession_summary`, `get_highlights`) provide concise summaries and anomaly detection to support a helper-first workflow and reduce expensive full-chain queries
- Tool for full posession-chain graph walks (`get_event_context`) after identifying key events from highlights.
- Docstring-based discovery (agent reads docstrings to understand capabilities)
- Response limits prevent context overflow on SLM
- Complete data guarantees: Each tool returns all relevant results (no incomplete subsets)

**Knowledge Graph** (StatsBomb Events)
- 3.5k+ events per match ingested into Neo4j
- Type-specific nodes: Pass, Shot, Pressure, Duel, Formation, etc.
- Possession chains linked temporally
- Player-team-formation relationships preserved
- Schema with constraints and indexes

**Prompt Engineering** (AI Engineering Focus)
- System prompt lists output guidelines and expectations
- ReAct prompt teaches agent to reason before acting
- Reflection prompt implements decision tree for continuation logic
- All prompts optimized for 1.7B parameter model (concise, structured, unambiguous)

**Test Isolation & Data Integrity**
- Tests don't corrupt production data (fixed critical pytest fixture bug)
- Automatic cleanup of test data after session
- 14 unit tests covering database, ingestion, client, and agent behaviors

WIP: Advanced visualization, streaming responses, multi-match analysis

## Stack

- **Agent Framework**: LangGraph 0.2+ (control flow + graph orchestration)
- **Knowledge Graph**: Neo4j 5-community (event nodes, possession chains, player relationships)
- **Data Source**: StatsBomb JSON (3.5k+ events per match)
- **Backend**: Flask in Python 3.12 + uv
- **LLM client**: OpenAI-compatible wrapper in `src/agent/llm_client.py` with a configurable, in-process rate limiter for safer LLM usage
- **Language Model**: Ollama qwen3:1.7b (1.7B parameters, local execution)
- **Frontend**: HTML/CSS/JS (minimal) — includes an agent-process trace visualizer and improved message handling (prevents stale "Analyzing" messages and keeps the user's question visible)

## Setup

### Prerequisites
- Docker + Docker Compose
- Python 3.12+
- uv (Python package manager)
- Ollama (for local LLM)

### Installation

```bash
# 1. Start Neo4j (knowledge graph backend)
docker-compose up -d

# 2. Install Python dependencies
uv sync

# 3. Start Ollama (in separate terminal for LLM inference)
ollama serve

# Pull the model (one time)
ollama pull qwen3:1.7b

# 5. Load StatsBomb data into Neo4j
uv run load_data.py --data-file data/18245.json --match-id match_18245 --clear
```

Verify setup:
```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Check Neo4j is ready
cypher-shell -u neo4j -p password 'RETURN "Neo4j ready" as msg'

# Run tests to verify agent system
uv run pytest tests/ -v
```

## Running the Agent

### Option 1: Web Interface (Recommended)
```bash
uv run python main.py
# Open http://localhost:5000 in browser
```
Minimal Flask frontend with match info display and interactive Q&A. Best way to interact with the agent.

### Option 2: Python API (For Programmatic Use)
```python
from src.agent import create_agent
from src.db import Neo4jClient

db = Neo4jClient("bolt://localhost:7687", "neo4j", "password")
agent = create_agent(db)

# Run agent analysis
result = agent.analyze("Who scored and how was the play built up?")
print(result)
```

## Testing

```bash
# Run all tests (with automatic test data cleanup)
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_client.py -v
```

## Example Agent Reasoning

**User Question**: "How was Bale's second goal scored?"

**Agent Thinking Process** (shown in CLI):
```
[THINK] Iteration 1
{
  "thinking": "User asked about the second goal. First find all goals to identify the second one",
  "action": "find_goals",
  "parameters": {}
}
[ACT] Calling find_goals({})
[ACT] Success: [{'event_id': '7654fe57-734f-45d8-bc83-ab940cd37c45', 'minute': 50, 'period': 2, 'scorer': 'Karim Benzema', 'team': 'Real Madrid', 'key_pass_id': None}, {'event_id': '53b73ee0-8c9c-4b64-83c5-69fc453376a1', 'minute': 54, 'period': 2, 'scorer': 'Sadio Mané', 'team': 'Liverpool', 'key_pass_id': None}, {'event_id': '36687201-f131-4418-9dd0-f632bc9c4257', 'minute': 63, 'period': 2, 'scorer': 'Gareth Frank Bale', 'team': 'Real Madrid', 'key_pass_id': 'ff375f8e-d488-4442-b7a6-73c7283fc371'}, {'event_id': '05688a6e-37f8-4aa6-a36e-d8151aa75997', 'minute': 82, 'period': 2, 'scorer': 'Gareth Frank Bale', 'team': 'Real Madrid', 'key_pass_id': 'c3ace7b4-1cb2-471b-b910-85322bd0dac8'}]

[REFLECT] Evaluating 1 result(s)
{
  "decision": "incomplete",
  "missing": "Need buildup context - call get_event_context(event_id) with second goal's event_id to get pass sequences"
}

[THINK] Iteration 3
{
  "thinking": "Found goal at minute 82. Now get buildup context",
  "action": "get_event_context",
  "parameters": {"event_id": "05688a6e-37f8-4aa6-a36e-d8151aa75997"}
}
[ACT] Calling get_event_context({'event_id': '05688a6e-37f8-4aa6-a36e-d8151aa75997'})
[ACT] Success: {'event': {'event_type': 'Shot', 'event_minute': 82, 'event_period': 2, 'event_outcome': 'Goal'}, 'buildup_chain': 'Sergio Ramos García → Marcelo Vieira da Silva Júnior → Marcelo Vieira da Silva Júnior → Cristiano Ronaldo dos Santos Aveiro → Cristiano Ronaldo dos Santos Aveiro → Marcelo Vieira da Silva Júnior → Marcelo Vieira da Silva Júnior → Gareth Frank Bale', 'buildup_passes': [{'from': 'Sergio Ramos García', 'to': 'Marcelo Vieira da Silva Júnior', 'minute': 82, 'second': 29, 'length': 17.962183, 'angle': -0.3287927, 'start_location': (45.8, 7.4), 'end_location': None}, {'from': 'Marcelo Vieira da Silva Júnior', 'to': 'Cristiano Ronaldo dos Santos Aveiro', 'minute': 82, 'second': 33, 'length': 14.1, 'angle': 0.0, 'start_location': (62.8, 1.6), 'end_location': None}, {'from': 'Cristiano Ronaldo dos Santos Aveiro', 'to': 'Marcelo Vieira da Silva Júnior', 'minute': 82, 'second': 35, 'length': 8.489994, 'angle': 2.3895154, 'start_location': (76.9, 1.6), 'end_location': None}, {'from': 'Marcelo Vieira da Silva Júnior', 'to': 'Gareth Frank Bale', 'minute': 82, 'second': 38, 'length': 54.98309, 'angle': 1.32273, 'start_location': (77.2, 14.5), 'end_location': None}], 'total_passes': 4}

[REFLECT] Evaluating 2 result(s)
{
  "decision": "complete",
  "reason": "Data contains 'buildup_chain' showing pass sequences leading to the goal"
}

[FINAL] Answer ready

[ANSWER] Generating final answer...
The second goal was scored by Gareth Frank Bale in the 82nd minute following a series of precise passes. The buildup involved a chain of passes from Sergio Ramos to Marcelo Vieira da Silva Júnior, then to Cristiano Ronaldo dos Santos Aveiro, culminating in a final pass to Bale, who converted the shot.
DEBUG: final_state is a dict: ['user_question', 'thoughts', 'tool_calls', 'tool_results', 'final_answer', 'confidence', 'parse_failures']

============================================================
Analysis complete in 4 iterations
============================================================
```

**User Question**: "which players passed to each other the most for liverpool?"

**Agent Thinking Process** (shown in CLI):
```
[THINK] Iteration 1
{
  "thinking": "User asked about passing partnerships for Liverpool. Use get_passing_pairs to retrieve passing partnerships for the team.",
  "action": "get_passing_pairs",
  "parameters": {"team": "Liverpool"}
}
[ACT] Calling get_passing_pairs({'team': 'Liverpool'})
[ACT] Success: [{'passer': 'Trent Alexander-Arnold', 'recipient': 'Roberto Firmino Barbosa de Oliveira', 'passes': 10}, {'passer': 'Virgil van Dijk', 'recipient': 'Andrew Robertson', 'passes': 10}, {'passer': 'Georginio Wijnaldum', 'recipient': 'Trent Alexander-Arnold', 'passes': 8}, {'passer': 'James Philip Milner', 'recipient': None, 'passes': 8}, {'passer': 'Andrew Robertson', 'recipient': 'Jordan Brian Henderson', 'passes': 7}, {'passer': 'Trent Alexander-Arnold', 'recipient': 'Mohamed Salah', 'passes': 7}, {'passer': 'Loris Karius', 'recipient': 'Dejan Lovren', 'passes': 7}, {'passer': 'Trent Alexander-Arnold', 'recipient': None, 'passes': 6}, {'passer': 'Jordan Brian Henderson', 'recipient': 'Sadio Mané', 'passes': 6}, {'passer': 'Andrew Robertson', 'recipient': 'Sadio Mané', 'passes': 6}]

[REFLECT] Evaluating 1 result(s)
{
  "decision": "complete",
  "reason": "Have complete list of pass interactions with counts per player, sufficient to identify top pairs (e.g., Trent Alexander-Arnold & Roberto Firmino with 10 passes each)"
}

[FINAL] Answer ready

[ANSWER] Generating final answer...
Trent Alexander-Arnold passed the most (10) to Roberto Firmino, while Virgil van Dijk also passed 10 to Andrew Robertson. Georginio Wijnaldum contributed 8 passes to Trent Alexander-Arnold, making them the top passers.
DEBUG: final_state is a dict: ['user_question', 'thoughts', 'tool_calls', 'tool_results', 'final_answer', 'confidence', 'parse_failures']

============================================================
Analysis complete in 2 iterations
============================================================
```

**Key Points Shown**:
1. **Think phase**: Agent reasons about what information is needed
2. **Act phase**: Agent calls tools (find_goals, get_possession_before_event)
3. **Reflect phase**: Agent evaluates tool results and decides to answer
4. **Answer phase**: Agent synthesizes findings into natural language

This iterative process continues until the agent has sufficient information or decides looping is unproductive.

## Project Structure

```
ai_tactico/
├── src/
│   ├── agent/                    # ★ AGENT SYSTEM (Core)
│   │   ├── agent.py              # LangGraph ReAct orchestrator (4-node graph)
│   │   ├── prompts.py            # System, ReAct, Reflection prompts (AI engineering)
│   │   ├── tools.py              # 9 tactical tools (docstring-based discovery)
│   │   ├── llm_client.py         # Ollama HTTP client
│   │   └── schemas.py            # Pydantic models (AgentState, ToolResult, etc.)
│   │
│   ├── db/                       # Knowledge Graph Layer
│   │   ├── client.py             # Neo4j connection & query runner
│   │   ├── schema.py             # Graph schema, constraints, indexes
│   │   └── ingest.py             # StatsBomb JSON → Neo4j ingestion
│   │
│   └── frontend/                 # Web UI (Optional, for testing)
│       ├── templates/index.html  # Q&A interface
│       └── static/
│           ├── app.js            # Client-side interaction
│           └── style.css         # Styling
│
├── tests/                        # Test Suite (14 tests)
│   ├── test_agent.py             # Agent reasoning tests
│   ├── test_tools.py             # Tool correctness tests
│   ├── conftest.py               # Fixtures (test isolation, cleanup)
│   └── ...
│
├── data/                         # StatsBomb match data (JSON)
├── main.py                       # Flask web app entry point
├── load_data.py                  # Data loader script
├── docker-compose.yml            # Neo4j infrastructure
└── pyproject.toml                # Dependencies (LangGraph, Neo4j, Flask, etc.)
```

### Architecture Highlights

**Agent System** (`src/agent/`):
- `agent.py`: LangGraph graph with conditional edges (think→act→reflect→answer)
  - Nodes: `_think_node` (LLM reasoning), `_act_node` (tool execution), `_reflect_node` (analysis), `_answer_node` (response)
  - Conditional edges: Act→Reflect (validate tool parsing), Reflect→Think or Answer (continue or finalize)
  - Early stopping: When "Final Answer:" detected, loop terminates
  - State management: `AgentState` (holds question, thoughts, actions, reflections, answer)
- `prompts.py`: AI engineering core
  - System prompt: Tells agent what it is, lists all 9 tools with signatures
  - ReAct prompt: Teaches reasoning before action, emphasizes docstrings
  - Reflection prompt: Decision tree (Is data complete? Is it tactical? Continue or finalize?)
- `tools.py`: 9 specialized Neo4j queries
  - find_goals, get_possession_stats, get_attacking_patterns, analyze_transitions
  - get_pass_network, analyze_defensive_organization, get_pressing_intensity
  - get_possession_before_event, get_team_formation
  - Docstring extraction (MCP pattern): Agent reads tool docstrings to discover capabilities
  - Response limits: LIMIT 10, 6, etc. for SLM efficiency

**Knowledge Graph** (`src/db/`):
- Event-centric schema: Pass, Shot, Pressure, Duel, etc.
- Possession chains linked temporally
- Player-team-formation relationships
- Constraints enforce data integrity

**Entry Points**:
- `main.py`: Flask web server (primary interface for agent interaction)
- `agent.py`: Interactive CLI (for development & debugging agent reasoning)

## AI Engineering Insights

**Agentic Reasoning Design**:
- Iterative think→act→reflect loop prevents hallucinations
- Conditional edges in LangGraph enable early stopping (no wasted iterations)
- Max iteration limit (10) prevents infinite loops while allowing complex reasoning

**Prompt Engineering for LLMs**:
- System prompt explicitly lists all tools (agent can't "invent" tools)
- ReAct prompt teaches structured reasoning before action
- Reflection prompt uses decision tree logic (Is data complete? Is answer ready?)
- All prompts optimized for 1.7B parameter model (concise, unambiguous, minimal fluff)

**Tool Design for Knowledge Graphs**:
- 9 specialized tools (not generic graph traversal): Each designed for specific tactical question
- Complete data guarantees: Tools return ALL relevant results (no arbitrary LIMIT 1 that causes incomplete answers)
- Response limits prevent context overflow: LIMIT 10 partnerships (top 10), LIMIT 6 defenders (top 6), etc.
- Docstring-based discovery (MCP pattern): Agent reads docstrings to understand tool capabilities

**Knowledge Graph Architecture**:
- Event-centric design (not generic graph): Every node type (Pass, Shot, Formation, Pressure) has semantic meaning for football
- Temporal linking preserves possession chains and transition sequences
- Constraint-based schema enforces data integrity (unique players, valid formations, etc.)

**SLM Optimization** (Small Language Models like 1.7B params):
- Tool results limited to prevent context overflow
- Prompts use direct, unambiguous language (not abstract metaphors)
- Few-shot examples in prompts teach by demonstration, not explanation
- Agent stops immediately on "Final Answer:" (no resummarization overhead)

## Performance Notes

- Model: Ollama qwen3:1.7b (1.7B parameters)
- Average analysis time: 5-15 seconds per question
- Database queries execute in <100ms
- Tool responses limited to prevent context overflow on SLM