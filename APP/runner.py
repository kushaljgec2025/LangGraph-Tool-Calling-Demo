import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
try:
    from .loader import discover_registry_tools
    from .orchestrator import build_orchestrator, LOG_FILE
except ImportError:
    from loader import discover_registry_tools
    from orchestrator import build_orchestrator, LOG_FILE

def serialize_message(msg):
    """Serialize LangChain message for JSON display."""
    msg_dict = {
        "type": msg.type,
        "content": msg.content
    }
    if hasattr(msg, "tool_calls") and msg.tool_calls:
        msg_dict["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"], "id": tc.get("id")}
            for tc in msg.tool_calls
        ]
    if hasattr(msg, "name") and msg.name:
        msg_dict["name"] = msg.name
    if hasattr(msg, "tool_call_id") and msg.tool_call_id:
        msg_dict["tool_call_id"] = msg.tool_call_id
    return msg_dict

def run_query_pipeline(user_query: str):
    """
    Executes LangGraph pipeline for user_query and records detailed animation steps.
    """
    tools_dir = Path(__file__).parent / "registry" / "tools"
    tools = discover_registry_tools(str(tools_dir))
    tool_map = {t.name: t for t in tools}

    app = build_orchestrator(tools)

    trace = []
    messages_history = [HumanMessage(content=user_query)]
    
    # Step 0: START -> AGENT
    trace.append({
        "step": len(trace) + 1,
        "from_node": "START",
        "to_node": "agent",
        "active_node": "START",
        "node_type": "start",
        "title": "Query Received",
        "description": f"Workflow started with query: \"{user_query}\"",
        "input_data": {"user_query": user_query},
        "output_data": {"initial_state": [serialize_message(m) for m in messages_history]},
        "current_messages": [serialize_message(m) for m in messages_history],
        "tool_details": None
    })

    # Stream graph updates
    inputs = {"messages": [HumanMessage(content=user_query)]}
    final_answer = ""
    iteration_count = 0
    max_iterations = 15

    for update in app.stream(inputs, stream_mode="updates"):
        iteration_count += 1
        if iteration_count > max_iterations:
            break

        for node_name, node_output in update.items():
            new_msgs = node_output.get("messages", [])
            
            if node_name == "agent":
                agent_msg = new_msgs[-1] if new_msgs else None
                if not agent_msg:
                    continue
                
                messages_history.append(agent_msg)
                
                # Check if agent requested tool calls
                if hasattr(agent_msg, "tool_calls") and agent_msg.tool_calls:
                    calls_summary = [f"{c['name']}({json.dumps(c['args'])})" for c in agent_msg.tool_calls]
                    trace.append({
                        "step": len(trace) + 1,
                        "from_node": "START" if len(trace) == 1 else "tools",
                        "to_node": "agent",
                        "active_node": "agent",
                        "node_type": "agent",
                        "title": "Agent (LLM) Decision",
                        "description": f"LLM decided to call {len(agent_msg.tool_calls)} tool(s): {', '.join(calls_summary)}",
                        "input_data": {
                            "context_messages_count": len(messages_history) - 1,
                            "last_received": serialize_message(messages_history[-2]) if len(messages_history) > 1 else None
                        },
                        "output_data": {
                            "decision": "CALL_TOOLS",
                            "tool_calls": agent_msg.tool_calls,
                            "thought": agent_msg.content or "Determined tool execution is needed"
                        },
                        "current_messages": [serialize_message(m) for m in messages_history],
                        "tool_details": {
                            "status": "pending_execution",
                            "calls": agent_msg.tool_calls
                        }
                    })

                    # Add conditional routing step to router/tools
                    for call in agent_msg.tool_calls:
                        t_name = call["name"]
                        trace.append({
                            "step": len(trace) + 1,
                            "from_node": "agent",
                            "to_node": t_name if t_name in tool_map else "tools",
                            "active_node": "router",
                            "node_type": "router",
                            "title": f"Routing to Tool: {t_name}",
                            "description": f"Conditional edge routes call to registered tool '{t_name}' with args {json.dumps(call['args'])}",
                            "input_data": {"selected_tool": t_name, "args": call["args"]},
                            "output_data": {"target_node": t_name},
                            "current_messages": [serialize_message(m) for m in messages_history],
                            "tool_details": {
                                "name": t_name,
                                "args": call["args"]
                            }
                        })
                else:
                    # Final synthesis
                    final_answer = agent_msg.content
                    trace.append({
                        "step": len(trace) + 1,
                        "from_node": "tools" if len(messages_history) > 2 else "START",
                        "to_node": "agent",
                        "active_node": "agent",
                        "node_type": "agent",
                        "title": "Agent Final Synthesis",
                        "description": "LLM analyzed all tool results and synthesized the final response.",
                        "input_data": {
                            "all_previous_tool_outputs": [serialize_message(m) for m in messages_history if m.type == "tool"]
                        },
                        "output_data": {
                            "decision": "FINISH",
                            "final_answer": final_answer
                        },
                        "current_messages": [serialize_message(m) for m in messages_history],
                        "tool_details": None
                    })

                    # Route to END
                    trace.append({
                        "step": len(trace) + 1,
                        "from_node": "agent",
                        "to_node": "END",
                        "active_node": "END",
                        "node_type": "end",
                        "title": "Workflow Completed",
                        "description": "Execution reached END node. Result returned to user.",
                        "input_data": {"final_answer": final_answer},
                        "output_data": {"status": "SUCCESS"},
                        "current_messages": [serialize_message(m) for m in messages_history],
                        "tool_details": None
                    })

            elif node_name == "tools":
                # Tools executed
                for t_msg in new_msgs:
                    messages_history.append(t_msg)
                    try:
                        parsed_content = json.loads(t_msg.content)
                    except:
                        parsed_content = t_msg.content

                    t_name = getattr(t_msg, "name", "tools")
                    trace.append({
                        "step": len(trace) + 1,
                        "from_node": t_name if t_name in tool_map else "tools",
                        "to_node": "agent",
                        "active_node": t_name if t_name in tool_map else "tools",
                        "node_type": "tool",
                        "title": f"Tool Output: {t_name}",
                        "description": f"Tool '{t_name}' completed execution and returned result: {json.dumps(parsed_content)}",
                        "input_data": {"tool_name": t_name},
                        "output_data": {
                            "tool_output": parsed_content,
                            "tool_call_id": getattr(t_msg, "tool_call_id", None)
                        },
                        "current_messages": [serialize_message(m) for m in messages_history],
                        "tool_details": {
                            "name": t_name,
                            "result": parsed_content
                        }
                    })

    return {
        "status": "success",
        "query": user_query,
        "final_answer": final_answer,
        "steps": trace,
        "total_steps": len(trace)
    }
