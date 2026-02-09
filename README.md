# AI Tactico

**An AI Engineering exploration of agentic reasoning over knowledge graphs.**

Football tactical analysis agent powered by **LangGraph ReAct**, Neo4j knowledge graphs, and specialized tool design. The agent performs iterative reasoning (think→act→reflect→answer) to answer complex tactical questions about football matches using StatsBomb event data.

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

### Key Agent Components

**LangGraph Graph** (`src/agent/agent.py`):
- 4-node directed graph: `_think_node` → `_act_node` → `_reflect_node` → `_answer_node`
- Conditional edges: `_act_node` validates tool parsing; `_reflect_node` decides loop continuation
- Early stopping: When agent produces "Final Answer:", loop terminates immediately
- Max iterations: Prevents infinite reasoning loops (currently 10)

**Prompt Engineering** (`src/agent/prompts.py`):
- **System Prompt**: Establishes agent persona as tactical analyst, lists all 9 available tools with signatures
- **ReAct Prompt**: Instructs agent on thought→action format, emphasizes tool docstrings as source of truth
- **Reflection Prompt**: Decision tree for tool result analysis (Is it factual? Complete? Tactical? Actionable?)

**Tool Discovery** (`src/agent/tools.py`):
- 9 specialized tools via Neo4j queries (not hardcoded, extracted from docstrings)
- MCP-style docstring-based discovery: Agent reads tool docstrings to understand capabilities
- Response limits optimized for qwen3:1.7b: LIMIT 10 partnerships, LIMIT 6 defenders, etc.

### Agent Flow in Practice

**Example: "Explain the buildup to the first goal"**

```
THINK: "I need to find the goal event first, then trace the possession chain leading to it"
  → Identified information needs: goal timing, possession sequence, formation context

ACT: Tool call → find_goals()
  Returns: [{"goal_id": 2345, "scorer": "Benzema", "minute": 50, ...}]

REFLE CT: "I have the goal, now I need the buildup. Is this enough? No, need possession chain."
  → Decision: Continue reasoning

ACT: Tool call → get_possession_before_event(event_id=2345)
  Returns: [Pass chain of 12 events leading to shot]

REFLECT: "Good, I have context but should verify tactical setup at goal time"
  → Decision: One more tool call needed

ACT: Tool call → get_team_formation(team_id=..., minute=50)
  Returns: Formation snapshot showing attacking positioning

REFLECT: "Sufficient data to explain. I have goal, buildup sequence, and formation context."
  → Decision: Answer now (Final Answer: ...)

ANSWER: "Benzema's goal at minute 50 came through a patient buildup where Real Madrid 
maintained width with fullback support. The final three passes shifted from lateral to 
vertical penetration, exploiting Bayern's narrow mid-block positioning..."
```

## Stack

- **Language Model**: Ollama qwen3:1.7b (1.7B parameters, local execution)
- **Agent Framework**: LangGraph 0.2+ (control flow + graph orchestration)
- **Knowledge Graph**: Neo4j 5-community (event nodes, possession chains, player relationships)
- **Data Source**: StatsBomb JSON (3.5k+ events per match)
- **Backend**: Python 3.12 + uv
- **Frontend**: Flask + HTML/CSS/JS (minimal, for interaction testing)

## Current Status

✓ **Agent System** (Core Focus)
- LangGraph graph compiles and executes correctly
- ReAct loop with proper conditional edges and early stopping
- Reflection mechanism validates tool results and decides continuation
- Handles malformed tool calls with error recovery
- Tests verify agent terminates after final answer (not looping excessively)

✓ **Tool System** (9 Specialized Queries)
- 9 Neo4j tools for football analysis (not general-purpose graph traversal)
- Each tool optimized for specific tactical question type
- Docstring-based discovery (agent reads docstrings to understand capabilities)
- Response limits prevent context overflow on SLM
- Complete data guarantees: Each tool returns all relevant results (no incomplete subsets)

✓ **Knowledge Graph** (StatsBomb Events)
- 3.5k+ events per match ingested into Neo4j
- Type-specific nodes: Pass, Shot, Pressure, Duel, Formation, etc.
- Possession chains linked temporally
- Player-team-formation relationships preserved
- Schema with constraints and indexes

✓ **Prompt Engineering** (AI Engineering Focus)
- System prompt lists all 9 tools explicitly
- ReAct prompt teaches agent to reason before acting
- Reflection prompt implements decision tree for continuation logic
- All prompts optimized for 1.7B parameter model (concise, structured, unambiguous)

✓ **Test Isolation & Data Integrity**
- Tests don't corrupt production data (fixed critical pytest fixture bug)
- Automatic cleanup of test data after session
- 14 unit tests covering database, ingestion, client, and agent behaviors

WIP: Advanced visualization, streaming responses, multi-match analysis

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

### Option 2: Interactive CLI (For Development)
```bash
uv run python agent.py
```
Prompts for tactical questions interactively. Shows agent's thinking → acting → reflecting process. Useful for debugging agent reasoning.

### Option 3: Python API (For Programmatic Use)
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

**User Question**: "How was the first goal scored?"

**Agent Thinking Process** (shown in CLI):
```
THINKING:
"To answer how the goal was scored, I need to:
1. Find the goal event and identify the scorer
2. Get the possession chain leading to the goal to understand the buildup
3. Check the formation at the time to understand tactical context"

ACTION: Tool Call → find_goals()
Result: Goal at minute 50 by Benzema (event_id: 2345)

THINKING:
"Good, I found the goal. Now I need the buildup sequence . Let me get
the possession chain before this goal event."

ACTION: Tool Call → get_possession_before_event(event_id=2345)
Result: 12 event possession chain showing passes and positioning

REFLECTION:
"I have the goal event and the buildup sequence. The data shows a
possession chain of 12 passes leading to Benzema's shot. I have
enough information to explain how the goal was scored."

FINAL ANSWER:
"Benzema scored at minute 50 through a coordinated team play. Real Madrid
controlled possession with 12 consecutive passes, maintaining 88% accuracy.
The buildup featured intelligent width play, pulling Bayern's defense wide
before a final vertical pass through the midfield released Benzema into
shooting space. His finish was clinical and unstoppable."
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
├── agent.py                      # CLI entry point (interactive agent)
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
- Event-centric schema: Pass, Shot, Pressure, Duel, Formation nodes
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

## Troubleshooting

### Data disappeared after running tests
- **Root cause**: Old pytest fixture cleared all data
- **Status**: FIXED - Now uses test IDs and auto-cleanup
- **Verification**: `uv run pytest tests/ -v` leaves only `match_18245` in DB

### Agent takes too long to respond
- Check if Ollama is running: `ollama serve` in separate terminal
- Verify model is pulled: `ollama list` should show `qwen3:1.7b`

### Database connection errors
- Ensure Neo4j is running: `docker-compose up -d`
- Check connection settings in `main.py` or `agent.py`
- Default: `bolt://localhost:7687` user: `neo4j` password: `password`
