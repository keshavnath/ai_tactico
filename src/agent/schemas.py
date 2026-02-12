"""Type definitions for agent."""
from typing import Any, Optional
from pydantic import BaseModel, Field


class PassData(BaseModel):
    """Single pass event."""
    player_name: str
    recipient_name: Optional[str] = None
    distance: float
    pass_type: str
    success: bool


class PossessionChain(BaseModel):
    """Analyzed possession sequence."""
    possession_id: int
    team: str
    duration_seconds: float
    start_minute: int
    passes: list[PassData]
    
    # Computed metrics
    completion_rate: float
    avg_pass_distance: float
    pressure_count: int
    direction_pattern: str  # e.g., "vertical", "lateral", "mixed"
    spatial_progression: str  # e.g., "defensive_to_attacking"
    
    # Tactical context
    tactical_notes: list[str] = Field(default_factory=list)


class EventContext(BaseModel):
    """Context around a specific event."""
    event_id: str
    event_type: str
    minute: int
    player: str
    team: str
    
    # Before/after events
    previous_events: list[dict] = Field(default_factory=list)
    next_events: list[dict] = Field(default_factory=list)


class FormationSnapshot(BaseModel):
    """Team formation at a point in time."""
    team: str
    formation: str  # e.g., "4-3-3"
    minute: int


class AgentState(BaseModel):
    """Internal state for ReAct agent."""
    user_question: str
    
    # Reasoning trace
    thoughts: list[str] = Field(default_factory=list)
    tool_calls: list[tuple[str, dict]] = Field(default_factory=list)  # (tool_name, args)
    tool_results: list[Any] = Field(default_factory=list)
    
    # Answer tracking
    final_answer: Optional[str] = None
    confidence: float = 0.0
    
    # Failure tracking (for debugging)
    parse_failures: int = 0  # Count of failed action parsing attempts


class ToolResult(BaseModel):
    """Structured result from a tool call."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    raw_query: Optional[str] = None  # For debugging
