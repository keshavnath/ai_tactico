# AI Tactico

Football match analysis AI agent using StatsBomb event data, Neo4j knowledge graphs, and agentic tactical reasoning.

## Stack

- **Data**: StatsBomb JSON event data
- **Database**: Neo4j (5-community) with APOC plugin
- **Backend**: Python 3.12, uv
- **Agent**: LangGraph ReAct with local Ollama LLM
- **Reasoning**: Football-specialized tactical analysis
- **Frontend**: Minimal web interface (WIP)

## Current State

✓ **Database Layer**: StatsBomb events ingested into Neo4j with full schema
- 3.5k+ events per match
- Players, teams, possessions, temporal event chains
- Type-specific Event nodes (Pass, Shot, Duel, etc.)
- Constraint-based schema with indexes

✓ **Agent Layer**: ReAct reasoning loop with tactical tools
- LangGraph-based agent for iterative reasoning
- Neo4j tools for graph traversal
- Football strategy-aware prompts
- Ollama integration for local LLM inference

WIP: MCP tools, frontend

## Setup

### Prerequisites
- Docker + Docker Compose
- Python 3.12+
- uv (Python package manager)
- Ollama (for local LLM)

### Installation & Run

```bash
# Start Neo4j
docker-compose up -d

# Install dependencies
uv sync

# Start Ollama (in separate terminal)
ollama serve

# Pull the model (one time)
ollama pull qwen3:1.7b

# Load match data
uv run load_data.py --data-file data/18245.json --match-id match_18245 --clear

# Run the agent
uv run agent.py

# Run tests
uv run pytest tests/ -v
```

## Example Agent Interaction

```
Ask about the match:
> Explain the buildup to the first goal

Analysis:
[Agent reasons through the match data, calling tools like:
 - find_goals() to locate the goal event
 - get_possession_before_event() to retrieve the possession chain
 - get_team_formation() to check tactical setup
 - get_pressing_intensity() to assess defensive activity]

Agent provides tactical insights:
"Team A's goal was orchestrated through intelligent possession control. 
They maintained 92% pass completion in the buildup, compressing the field 
against Team B's mid-block. The transition came in the final 3 passes—
a shift from lateral play to vertical penetration, exploiting the width 
that Team B's narrow formation had vacated..."
```

## Project Structure

```
ai_tactico/
├── src/
│   ├── db/
│   │   ├── client.py       # Neo4j connection manager
│   │   ├── schema.py       # Graph constraints & indexes
│   │   └── ingest.py       # StatsBomb ingestion
│   └── agent/
│       ├── agent.py        # LangGraph ReAct loop
│       ├── tools.py        # Tactical graph tools
│       ├── llm_client.py   # Ollama HTTP client
│       ├── prompts.py      # System prompts
│       └── types.py        # Pydantic models
├── tests/                  # Unit tests (database layer)
├── data/                   # StatsBomb match data
├── agent.py                # Agent entry point
├── load_data.py            # Data loader script
├── docker-compose.yml      # Neo4j + infrastructure
└── pyproject.toml          # Dependencies
