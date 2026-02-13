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
            self._should_continue_from_act,
            {
                "reflect": "reflect",
                "think": "think",
                "end": END,
            }
        )
        # After reflect, determine if we have complete data or need more
        workflow.add_conditional_edges(
            "reflect",
            self._should_continue_from_reflect,
            {
                "think": "think",     # Need more data, continue thinking
                "answer": "answer",   # Have complete data, generate answer
                "end": END,           # Error case, stop
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
        
        # Try to parse JSON from response
        try:
            # Extract JSON object from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', last_thought, re.DOTALL)
            if not json_match:
                state.parse_failures += 1
                print("[ACT] ERROR: No JSON found in response")
                print(f"[ACT] Expected JSON with 'action' and 'parameters' fields")
                print(f"[ACT] Got: {last_thought[:200]}")
                print(f"[ACT] Parse failures: {state.parse_failures}/3")
                
                if state.parse_failures >= 3:
                    print("[ACT] STOPPING: Too many parse failures. Model not outputting valid JSON.")
                    state.final_answer = "I encountered an issue processing your question. Model could not produce JSON-formatted responses after 3 attempts."
                    return state
                
                return state
            
            json_str = json_match.group(0)
            action_data = json.loads(json_str)
            
            # Validate required fields
            if "action" not in action_data:
                state.parse_failures += 1
                print("[ACT] ERROR: Missing 'action' field in JSON")
                print(f"[ACT] Got: {action_data}")
                print(f"[ACT] Parse failures: {state.parse_failures}/3")
                
                if state.parse_failures >= 3:
                    print("[ACT] STOPPING: Too many parse failures.")
                    state.final_answer = "I encountered an issue with action parsing."
                    return state
                
                return state
            
            if "parameters" not in action_data:
                state.parse_failures += 1
                print("[ACT] ERROR: Missing 'parameters' field in JSON")
                print(f"[ACT] Got: {action_data}")
                print(f"[ACT] Parse failures: {state.parse_failures}/3")
                
                if state.parse_failures >= 3:
                    print("[ACT] STOPPING: Too many parse failures.")
                    state.final_answer = "I encountered an issue with action parsing."
                    return state
                
                return state
            
            # Reset parse failures on successful parse
            state.parse_failures = 0
            
            tool_name = action_data["action"]
            tool_input = action_data["parameters"]
            
            # Validate tool exists
            valid_tools = [t["name"] for t in tools.list_available_tools()]
            if tool_name not in valid_tools:
                print(f"[ACT] ERROR: Tool '{tool_name}' not found")
                print(f"[ACT] Available tools: {', '.join(valid_tools)}")
                state.parse_failures += 1
                return state
            
            # Execute tool
            print(f"[ACT] Calling {tool_name}({tool_input})")
            tool_func = getattr(tools, tool_name, None)
            
            try:
                result = tool_func(self.db, **tool_input)
                if result.success:
                    data_preview = str(result.data)
                    print(f"[ACT] Success: {data_preview}")
                else:
                    print(f"[ACT] Tool error: {result.error}")
            except Exception as e:
                result = ToolResult(success=False, error=f"Execution failed: {str(e)}")
                print(f"[ACT] Execution error: {e}")

            # Ensure a pretty-printed textual representation exists for LLM consumption.
            try:
                pretty = json.dumps(result.data, indent=2, ensure_ascii=False, default=str)
            except Exception:
                pretty = str(result.data) if result.data is not None else None

            # Build a concise summary line for quick scanning by the LLM
            summary = ""
            try:
                if isinstance(result.data, list):
                    count = len(result.data)
                    if count > 0 and isinstance(result.data[0], dict):
                        sample_keys = list(result.data[0].keys())[:4]
                        summary = f"{count} items — keys: {', '.join(sample_keys)}"
                    else:
                        summary = f"{count} items"
                elif isinstance(result.data, dict):
                    ks = list(result.data.keys())[:6]
                    summary = f"keys: {', '.join(ks)}"
                elif result.data is None:
                    summary = "no data"
                else:
                    summary = ""
            except Exception:
                summary = ""

            if pretty:
                if summary:
                    result.data_pretty = f"SUMMARY: {summary}\nFULL_DATA_START\n{pretty}\nFULL_DATA_END"
                else:
                    result.data_pretty = f"FULL_DATA_START\n{pretty}\nFULL_DATA_END"
            else:
                # If no structured data, surface the error or raw query for debugging
                if result.error:
                    result.data_pretty = f"ERROR: {result.error}"
                elif getattr(result, 'raw_query', None):
                    result.data_pretty = f"RAW_QUERY:\n{result.raw_query}"
                else:
                    result.data_pretty = None

            state.tool_calls.append((tool_name, tool_input))
            state.tool_results.append(result)
            
            return state
            
        except json.JSONDecodeError as e:
            state.parse_failures += 1
            print("[ACT] ERROR: Invalid JSON in response")
            print(f"[ACT] Parse error: {str(e)}")
            print(f"[ACT] Got: {last_thought[:200]}")
            print(f"[ACT] Parse failures: {state.parse_failures}/3")
            
            if state.parse_failures >= 3:
                print("[ACT] STOPPING: Too many parse failures.")
                state.final_answer = "I encountered an issue with JSON parsing. Please try again."
                return state
            
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
        
        # Parse JSON response from reflection
        try:
            json_match = re.search(r'\{.*\}', reflection, re.DOTALL)
            if json_match:
                reflection_data = json.loads(json_match.group(0))
                
                if reflection_data.get("decision") == "complete":
                    # We have all data needed - ready to answer
                    state.final_answer = "ready_to_answer"
                    print(f"\n[FINAL] Answer ready")
                elif reflection_data.get("decision") == "incomplete":
                    # Need more data - continue looping (don't set final_answer)
                    pass
        except (json.JSONDecodeError, AttributeError):
            # If JSON parsing fails, try to infer from text
            print("[REFLECT] Warning: Could not parse JSON, attempting text fallback")
            if "complete" in reflection.lower():
                state.final_answer = "ready_to_answer"
                print(f"\n[FINAL] Answer ready (from text fallback)")
        
        return state
    
    def _answer_node(self, state: AgentState) -> AgentState:
        """Final answer synthesis."""
        # Generate final answer based on tool results
        print(f"\n[ANSWER] Generating final answer...")
        
        # Check if we have any successful tool results
        successful_results = [r for r in state.tool_results if r.success]
        
        if successful_results:
            context = "Information gathered:\n"
            for result in successful_results:
                context += f"- {result.data}\n"
        else:
            context = "No data was successfully retrieved."
        
        # Use a simple generation prompt for final answer
        answer_prompt = f"""Based on this data, provide a brief answer (1-3 sentences) to the question.

Question: {state.user_question}

Data: {context}

Answer:"""
        
        try:
            final_answer = self.llm.generate(
                answer_prompt,
                system=FOOTBALL_ANALYST_SYSTEM_PROMPT,
            )
            state.final_answer = final_answer.strip()
            print(f"{final_answer}")
        except Exception as e:
            print(f"[ANSWER] ERROR generating answer: {e}")
            state.final_answer = f"Unable to generate answer: {str(e)}"
        
        return state
    
    def _should_continue_from_act(self, state: AgentState) -> str:
        """Decide routing after act node."""
        # Hard limit on iterations
        if len(state.tool_calls) >= self.max_iterations:
            print(f"\n[STOP] Max iterations ({self.max_iterations}) reached")
            return "end"
        
        # If tool executed successfully and we have results, go to reflect
        if len(state.tool_results) > 0 and len(state.tool_results) >= len(state.tool_calls):
            return "reflect"
        
        # If no results (parsing error or tool failed), try thinking again
        return "think"
    
    def _should_continue_from_reflect(self, state: AgentState) -> str:
        """Decide routing after reflect node - check if we have complete data or need more."""
        # Check if final_answer was set (means reflection decided "complete")
        if state.final_answer == "ready_to_answer":
            return "answer"
        
        # Check last reflection thought for decision
        last_thought = state.thoughts[-1] if state.thoughts else ""
        
        try:
            json_match = re.search(r'\{.*\}', last_thought, re.DOTALL)
            if json_match:
                reflection_data = json.loads(json_match.group(0))
                if reflection_data.get("decision") == "complete":
                    return "answer"
                elif reflection_data.get("decision") == "incomplete":
                    return "think"  # Need more data, think about next tool
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Default: if we can't parse, assume need more data
        if len(state.tool_calls) < self.max_iterations:
            return "think"
        else:
            return "end"
    
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
