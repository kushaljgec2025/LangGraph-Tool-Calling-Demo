import os
from langchain_core.messages import HumanMessage
from loader import discover_registry_tools
from orchestrator import build_orchestrator, log_event, LOG_FILE

def main():
    # 1. Reset log file for a clean demo run
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")  # clear previous logs

    print("=== 1. Discovering Tools from Registry ===")
    tools = discover_registry_tools("registry/tools")
    for tool in tools:
        print(f" -> Loaded: {tool.name}")

    if not tools:
        print("No tools found in registry/tools. Exiting.")
        return

    # 2. Compile Orchestrator
    print("\n=== 2. Compiling LangGraph Orchestrator ===")
    app = build_orchestrator(tools)

    # 3. User Goal Query
    user_query = (
        "I bought 3 mechanical keyboards priced at $50 each. "
        "I applied a 10% holiday promo code, and state sales tax is 8%. "
        "What is my final checkout total?"
    )

    print(f"\nUser Query:\n\"{user_query}\"\n")
    log_event("USER_QUERY", {"query": user_query})

    # 4. Stream execution
    print("=== 3. Running Execution Pipeline ===")
    inputs = {"messages": [HumanMessage(content=user_query)]}
    final_answer = ""

    for event in app.stream(inputs, stream_mode="values"):
        latest_msg = event["messages"][-1]

        # Tool calls triggered by LLM
        if hasattr(latest_msg, "tool_calls") and latest_msg.tool_calls:
            for tc in latest_msg.tool_calls:
                print(f"  👉 [Action] Calling '{tc['name']}' with args: {tc['args']}")
        # Tool outputs
        elif latest_msg.type == "tool":
            print(f"  📥 [Result] {latest_msg.content}")
        # Final answer synthesized by agent
        elif latest_msg.type == "ai" and not latest_msg.tool_calls:
            final_answer = latest_msg.content

    print(f"\n=== 4. Final Answer ===\n{final_answer}")
    log_event("FINAL_ANSWER", {"answer": final_answer})
    print(f"\n[Done] Complete execution trace and results logged to '{LOG_FILE}'.")

if __name__ == "__main__":
    main()