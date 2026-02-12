"""ReAct agent for tactical analysis using LangGraph."""
import json
import re
from typing import Any, Optional
from langgraph.graph import StateGraph, END
from src.db import Neo4jClient
from .schemas import AgentState, ToolResult
from .llm_client import LLMClient
from . import tools
from .prompts import FOOTBALL_ANALYST_SYSTEM_PROMPT, get_react_prompt, get_reflection_prompt, format_iteration_history


class TacticalAgent:
    """ReAct agent for match analysis."""
    
    def __init__(
        self,
        db_client: Neo4jClient,
        llm_client: LLMClient,
        max_iterations: int = 10,
    ):
        self.db = db_client
        self.llm = llm_client
        self.max_iterations = max_iterations
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
                "think": "think",
                "end": END,
            }
        )
        # After reflect, check if we should continue
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue,
            {
                "think": "think",     # Continue to thinking step if missing data
                "reflect": "reflect", # Loop back to reflect (shouldn't happen)
                "end": END,           # Or stop if final answer is ready
            }
        )
        workflow.add_edge("answer", END)
        
        workflow.set_entry_point("think")
        
        return workflow.compile()
    
    def _think_node(self, state: AgentState) -> AgentState:
        """Thinking step: decide what to do next."""
        available_tools = tools.list_available_tools()
        
        # Format history of previous iterations for context
        history = format_iteration_history(
            state.thoughts,
            state.tool_calls,
            state.tool_results,
        )
        
        prompt = get_react_prompt(
            state.user_question,
            available_tools,
            iteration_history=history,
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
        
        # Check for multiple Actions in one output (violation of format)
        action_count = len(re.findall(r"Action:\s*\w+", last_thought, re.IGNORECASE))
        if action_count > 1:
            print(f"[ACT] WARNING: Found {action_count} actions in one response (should be 1)")
            print(f"[ACT] Model is not following format. Only using first action.")
        
        # Parse tool call from LLM thought - only get FIRST action
        action_match = re.search(r"Action:\s*(\w+)", last_thought, re.IGNORECASE)
        
        if not action_match:
            state.parse_failures += 1
            print("[ACT] ERROR: No 'Action:' found in response")
            print("[ACT] Expected format: Action: [tool_name]")
            # print(f"[ACT] Received: {last_thought[:150]}...")
            print(f"[ACT] Received: {last_thought}")
            print(f"[ACT] Parse failures: {state.parse_failures}/3")
            
            if state.parse_failures >= 3:
                print("[ACT] STOPPING: Too many parse failures. Model not following format.")
                state.final_answer = "I encountered an issue processing your question. Please rephrase or try a simpler question."
                return state
            
            return state
        
        # Find Action Input after the found Action
        action_pos = action_match.start()
        remaining_text = last_thought[action_pos:]
        input_match = re.search(
            r"Action Input:\s*(\{)",
            remaining_text,
            re.IGNORECASE
        )
        
        if not input_match:
            state.parse_failures += 1
            print("[ACT] ERROR: No 'Action Input:' JSON found in response")
            print("[ACT] Expected format: Action Input: {} or {'param': value}")
            print(f"[ACT] Parse failures: {state.parse_failures}/3")
            
            if state.parse_failures >= 3:
                print("[ACT] STOPPING: Too many parse failures.")
                state.final_answer = "I encountered an issue with action parsing. Please try again."
                return state
            
            return state
        
        # Reset parse failures on successful parse
        state.parse_failures = 0
        
        # Extract JSON by counting braces - find complete JSON object
        json_start = action_pos + input_match.start(1)  # Position of first '{'
        brace_count = 0
        json_end = None
        
        for i in range(json_start, len(last_thought)):
            if last_thought[i] == '{':
                brace_count += 1
            elif last_thought[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    json_end = i + 1
                    break
        
        if json_end is None:
            print("[ACT] ERROR: Incomplete JSON - mismatched braces")
            print("[ACT] Got: " + last_thought[json_start:json_start+100])
            state.parse_failures += 1
            return state
        
        json_str = last_thought[json_start:json_end]
        tool_name = action_match.group(1)
        
        # Validate tool exists
        valid_tools = [t["name"] for t in tools.list_available_tools()]
        if tool_name not in valid_tools:
            print(f"[ACT] ERROR: Tool '{tool_name}' not found")
            print(f"[ACT] Available tools: {', '.join(valid_tools)}")
            state.parse_failures += 1
            return state
        
        # Parse JSON input
        try:
            tool_input = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[ACT] ERROR: Invalid JSON in Action Input")
            print(f"[ACT] Parse error: {str(e)}")
            print(f"[ACT] Got: {json_str[:100]}")
            state.parse_failures += 1
            return state
        
        # Auto-inject period default if missing
        if tool_name == "get_pressing_intensity" and "period" not in tool_input:
            tool_input["period"] = 1
        
        # Execute tool
        print(f"[ACT] Calling {tool_name}({tool_input})")
        tool_func = getattr(tools, tool_name, None)
        
        try:
            result = tool_func(self.db, **tool_input)
            if result.success:
                data_preview = str(result.data)#[:100]
                print(f"[ACT] Success: {data_preview}")
            else:
                print(f"[ACT] Tool error: {result.error}")
        except Exception as e:
            result = ToolResult(success=False, error=f"Execution failed: {str(e)}")
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
        
        # Check if we should finalize answer (must match exact pattern at line start)
        # Parse reflection to find decision: "Final Answer: ..." or "Missing: ..."
        final_answer_match = re.search(r"^\s*Final Answer:\s*(.*?)\s*$", reflection, re.MULTILINE | re.IGNORECASE)
        missing_match = re.search(r"^\s*Missing:\s*(.*?)\s*$", reflection, re.MULTILINE | re.IGNORECASE)
        
        if final_answer_match:
            # Only treat as final if "Final Answer:" appears without "Missing:" in same line
            answer_line = final_answer_match.group(0)
            if "missing:" not in answer_line.lower():
                state.final_answer = final_answer_match.group(1).strip()
                print(f"\n[FINAL] Answer ready")
        elif missing_match:
            # Missing data - will continue looping
            pass
        
        return state
    
    def _answer_node(self, state: AgentState) -> AgentState:
        """Final answer synthesis."""
        if not state.final_answer:
            print(f"\n[ANSWER] Synthesizing final response...")
            
            # Check if we have any successful tool results
            successful_results = [r for r in state.tool_results if r.success]
            failed_results = [r for r in state.tool_results if not r.success]
            
            context = ""
            if successful_results:
                context = "Information gathered:\n"
                for result in successful_results:
                    context += f"- {result.data}\n"
            elif failed_results:
                context = "Data unavailable:\n"
                for result in failed_results:
                    context += f"- {result.error}\n"
            else:
                context = "No tools were successfully executed."
            
            synthesis_prompt = get_react_prompt(
                state.user_question,
                tools.list_available_tools(),
                done_reasoning=True,
            )
            
            try:
                final_analysis = self.llm.generate(
                    f"{context}\n\n{synthesis_prompt}",
                    system=FOOTBALL_ANALYST_SYSTEM_PROMPT,
                )
                state.final_answer = final_analysis
                print(f"{final_analysis}")
            except Exception as e:
                print(f"[ANSWER] ERROR synthesizing answer: {e}")
                state.final_answer = f"Unable to synthesize answer: {str(e)}"
        else:
            # Final answer was set earlier (e.g., due to parsing errors or reflection)
            print(f"\n[FINAL] Answer ready")
            print(f"{state.final_answer}")
        
        return state
    
    def _should_continue(self, state: AgentState) -> str:
        """Decide if we should continue reasoning or finalize answer."""
        # Hard limit on iterations
        if len(state.tool_calls) >= self.max_iterations:
            print(f"\n[STOP] Max iterations ({self.max_iterations}) reached")
            return "end"
        
        # If we have a final answer, stop
        if state.final_answer:
            return "end"
        
        # Check last thought
        last_thought = state.thoughts[-1] if state.thoughts else ""
        
        # If LLM explicitly said "Final Answer:", stop
        if "Final Answer:" in last_thought:
            return "end"
        
        # If LLM said "Missing:" data, continue to thinking/acting to find that data
        if "Missing:" in last_thought and len(state.tool_calls) > 0:
            return "think"
        
        # If we just tried a tool and got results after a reflection, synthesize answer
        if len(state.tool_results) > len(state.tool_calls):
            # This shouldn't happen, but if it does, go to answer
            return "end"
        
        # Default: go to reflection step
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
        final_state = self.graph.invoke(initial_state)
        
        # Debug: check final state type
        if isinstance(final_state, dict):
            print(f"DEBUG: final_state is a dict: {list(final_state.keys())}")
            # Try to extract from dict
            if "thoughts" in final_state:
                num_iterations = len(final_state["thoughts"])
            else:
                num_iterations = 0
            final_answer = final_state.get("final_answer", "Unable to generate analysis")
        else:
            num_iterations = len(final_state.thoughts)
            final_answer = final_state.final_answer or "Unable to generate analysis"
        
        print(f"\n{'='*60}")
        print(f"Analysis complete in {num_iterations} iterations")
        print(f"{'='*60}\n")
        
        return final_answer


def create_agent(
    db_client: Neo4jClient,
    llm_base_url: Optional[str] = None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    max_iterations: int = 10,
) -> TacticalAgent:
    """Factory function to create a configured agent.
    
    Args:
        db_client: Neo4j database client
        llm_base_url: LLM API endpoint (defaults to LLM_BASE_URL env var)
        llm_model: Model identifier (defaults to LLM_MODEL env var)
        llm_api_key: API key for LLM (defaults to LLM_API_KEY env var)
        max_iterations: Max ReAct iterations before stopping (default: 10)
        
    Returns:
        Configured TacticalAgent instance
    """
    llm = LLMClient(
        base_url=llm_base_url,
        model=llm_model,
        api_key=llm_api_key,
    )
    return TacticalAgent(db_client, llm, max_iterations=max_iterations)
