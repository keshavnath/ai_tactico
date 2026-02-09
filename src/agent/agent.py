"""ReAct agent for tactical analysis using LangGraph."""
import json
import re
from typing import Any, Optional
from langgraph.graph import StateGraph, END
from src.db import Neo4jClient
from .schemas import AgentState, ToolResult
from .llm_client import LLMClient
from . import tools
from .prompts import FOOTBALL_ANALYST_SYSTEM_PROMPT, get_react_prompt, get_reflection_prompt


class TacticalAgent:
    """ReAct agent for match analysis."""
    
    def __init__(
        self,
        db_client: Neo4jClient,
        llm_client: LLMClient,
    ):
        self.db = db_client
        self.llm = llm_client
        self.max_iterations = 10
        self.graph = self._build_graph()
    
    def _build_graph(self):
        """Build LangGraph ReAct workflow."""
        workflow = StateGraph(AgentState)
        
        # Nodes
        workflow.add_node("think", self._think_node)
        workflow.add_node("act", self._act_node)
        workflow.add_node("reflect", self._reflect_node)
        workflow.add_node("answer", self._answer_node)
        
        # Edges
        workflow.add_edge("think", "act")
        workflow.add_conditional_edges(
            "act",
            self._should_continue,
            {
                "reflect": "reflect",
                "end": END,
            }
        )
        workflow.add_edge("reflect", "think")
        workflow.add_edge("answer", END)
        
        workflow.set_entry_point("think")
        
        return workflow.compile()
    
    def _think_node(self, state: AgentState) -> AgentState:
        """Thinking step: decide what to do next."""
        available_tools = tools.list_available_tools()
        prompt = get_react_prompt(
            state.user_question,
            available_tools,
        )
        
        print(f"\n[THINK] Iteration {len(state.thoughts) + 1}")
        thought = self.llm.generate(
            prompt,
            system=FOOTBALL_ANALYST_SYSTEM_PROMPT,
        )
        
        print(f"{thought}")
        state.thoughts.append(thought)
        return state
    
    def _act_node(self, state: AgentState) -> AgentState:
        """Action step: execute a tool based on reasoning."""
        last_thought = state.thoughts[-1] if state.thoughts else ""
        
        # Parse tool call from LLM thought
        action_match = re.search(r"Action:\s*(\w+)", last_thought, re.IGNORECASE)
        input_match = re.search(
            r"Action Input:\s*({.*})",
            last_thought,
            re.IGNORECASE | re.DOTALL
        )
        
        if not action_match or not input_match:
            print("[ACT] No tool call found in thought")
            return state
        
        tool_name = action_match.group(1)
        try:
            tool_input = json.loads(input_match.group(1))
        except json.JSONDecodeError:
            print(f"[ACT] Failed to parse tool input")
            return state
        
        if tool_name == "get_pressing_intensity" and "period" not in tool_input:
            tool_input["period"] = 1
        
        print(f"[ACT] Calling {tool_name}({tool_input})")
        tool_func = getattr(tools, tool_name, None)
        if not tool_func:
            result = ToolResult(success=False, error=f"Unknown tool: {tool_name}")
            print(f"[ACT] ERROR: Unknown tool")
        else:
            try:
                result = tool_func(self.db, **tool_input)
                if result.success:
                    data_preview = str(result.data)[:100]
                    print(f"[ACT] Success: {data_preview}")
                else:
                    print(f"[ACT] Tool error: {result.error}")
            except TypeError as e:
                result = ToolResult(success=False, error=f"Tool call error: {str(e)}")
                print(f"[ACT] Execution error: {e}")
        
        state.tool_calls.append((tool_name, tool_input))
        state.tool_results.append(result)
        
        return state
    
    def _reflect_node(self, state: AgentState) -> AgentState:
        """Reflection step: evaluate results and decide next action."""
        if not state.tool_results:
            return state
        
        # Summarize all tool results
        result_summaries = []
        for result in state.tool_results:
            if result.success:
                result_summaries.append(f"Tool result: {result.data}")
            else:
                result_summaries.append(f"Tool error: {result.error}")
        
        print(f"\n[REFLECT] Evaluating {len(result_summaries)} result(s)")
        
        reflection_prompt = get_reflection_prompt(
            state.user_question,
            result_summaries,
        )
        
        reflection = self.llm.generate(
            reflection_prompt,
            system=FOOTBALL_ANALYST_SYSTEM_PROMPT,
        )
        
        print(f"{reflection}")
        
        state.thoughts.append(reflection)
        
        # Check if we should finalize answer
        if "Final Answer:" in reflection:
            state.final_answer = reflection.split("Final Answer:")[-1].strip()
            print(f"\n[FINAL] Answer ready")
        
        return state
    
    def _answer_node(self, state: AgentState) -> AgentState:
        """Final answer synthesis."""
        if not state.final_answer:
            print(f"\n[ANSWER] Synthesizing final response...")
            synthesis_prompt = get_react_prompt(
                state.user_question,
                tools.list_available_tools(),
                done_reasoning=True,
            )
            
            # Append tool results to context
            context = "Information gathered:\n"
            for result in state.tool_results:
                if result.success:
                    context += f"- {result.data}\n"
            
            final_analysis = self.llm.generate(
                f"{context}\n\n{synthesis_prompt}",
                system=FOOTBALL_ANALYST_SYSTEM_PROMPT,
            )
            
            state.final_answer = final_analysis
            print(f"{final_analysis}")
        
        return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Decide if we should continue reasoning or finalize answer."""
        if len(state.tool_calls) >= self.max_iterations:
            return "end"
        
        if state.final_answer:
            return "end"
        
        last_thought = state.thoughts[-1] if state.thoughts else ""
        if "Final Answer:" in last_thought:
            return "end"
        
        return "reflect"
    
    def analyze(self, question: str) -> str:
        """Run the agent to analyze a question about the current match.
        
        Args:
            question: The tactical question to analyze
        """
        print(f"\n{'='*60}")
        print(f"QUESTION: {question}")
        print(f"{'='*60}")
        
        initial_state = AgentState(user_question=question)
        final_state: AgentState = self.graph.invoke(initial_state)
        
        print(f"\n{'='*60}")
        print(f"Analysis complete in {len(final_state.thoughts)} iterations")
        print(f"{'='*60}\n")
        
        return final_state.final_answer or "Unable to generate analysis"


def create_agent(
    db_client: Neo4jClient,
    llm_base_url: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> TacticalAgent:
    """Factory function to create a configured agent."""
    llm = LLMClient(base_url=llm_base_url, model=llm_model)
    return TacticalAgent(db_client, llm)
