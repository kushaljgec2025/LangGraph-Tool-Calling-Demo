import os
import json
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, ToolMessage

from loader import discover_registry_tools

load_dotenv()

# 1. Discover all tools from registry/tools
tools = discover_registry_tools("registry/tools")

print("Available Tools:")
for tool in tools:
    print(f"- {tool.name}: {tool.description}")

# 2. Initialize Gemini
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0
)

# 3. Bind tools to Gemini
llm_with_tools = llm.bind_tools(tools)

# 4. Send user query
messages = [
    HumanMessage(content="Calculate 10 * 20 using the available calculator tool.")
]

response = llm_with_tools.invoke(messages)

# 5. Check whether Gemini requested any tools
print("\nGemini Tool Calls:")
print(response.tool_calls)

# 6. Execute the requested tools
tool_map = {tool.name: tool for tool in tools}
tool_messages = []

for call in response.tool_calls:
    name = call["name"]
    args = call["args"]

    print(f"\nExecuting Tool: {name}")
    print("Arguments:", args)

    result = tool_map[name].invoke(args)

    print("Tool Output:", result)

    tool_messages.append(
        ToolMessage(
            content=json.dumps(result, default=str),
            name=name,
            tool_call_id=call["id"]
        )
    )

# 7. Send tool results back to Gemini
if tool_messages:
    messages.extend([response, *tool_messages])

    final_response = llm_with_tools.invoke(messages)

    print("\nFinal Response:")
    print(final_response.content)

else:
    print("\nFinal Response:")
    print(response.content)