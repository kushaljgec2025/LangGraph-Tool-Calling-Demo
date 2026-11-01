import json
import os
from datetime import datetime
from dotenv import load_dotenv
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
load_dotenv()
LOG_FILE = "log.txt"

def log_event(event_type: str, payload: dict):
    """Appends an event timestamp and formatted JSON payload to log.txt."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": payload
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def build_orchestrator(tools: list, model_name: str = "gemini-3.1-flash-lite"):
    tool_map = {t.name: t for t in tools}
    
    # Initialize Google Gemini model according Langchain
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=os.environ.get("GEMINI_API_KEY")
    )
    # Bind tools to the LLM so it can use them
    """
    Basically we are exposing all the tool to the LLM using a structured format
    which llm can understand and use it to generate the response
    """
    llm_with_tools = llm.bind_tools(tools)

    """
    state : This is basically our custom state manager for our langgraph.
    """

    
    def agent_node(state: AgentState):
        """Calls the LLM and logs the decision."""
        response = llm_with_tools.invoke(state["messages"])

        # Extract tool call metadata if present
        tool_calls_info = [
            {"name": tc["name"], "args": tc["args"]}
            for tc in getattr(response, "tool_calls", [])
        ]
        log_event("LLM_CALL", {
            "content": response.content,
            "tool_calls": tool_calls_info
        })
        return {"messages": [response]}

    def tool_node(state: AgentState):
        """Executes tool calls sequentially and logs inputs and outputs."""
        last_message = state["messages"][-1]
        tool_messages = []

        for call in getattr(last_message, "tool_calls", []):
            name = call["name"]
            args = call["args"]
            tool = tool_map.get(name)

            if tool is None:
                output = {"error": f"Tool '{name}' not found."}
            else:
                try:
                    output = tool.invoke(args)
                except Exception as e:
                    output = {"error": str(e), "status": "error"}

            # Log tool execution trace
            log_event("TOOL_EXECUTION", {
                "tool": name,
                "input_args": args,
                "output": output
            })

            tool_messages.append(
                ToolMessage(
                    content=json.dumps(output),
                    name=name,
                    tool_call_id=call["id"]
                )
            )

        return {"messages": tool_messages}

    def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"
        return END

    # Build LangGraph workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, ["tools", END])
    workflow.add_edge("tools", "agent")

    return workflow.compile()