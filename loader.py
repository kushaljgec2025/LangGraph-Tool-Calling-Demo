import os
import json
import importlib.util
from pathlib import Path
from pydantic import create_model, Field
from langchain_core.tools import StructuredTool

# Map JSON schema types to Python types
TYPE_MAPPING = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool
}

# ------------------------------------------------
# Take a tool directory -> Langchain Structured Tool
# -----
def load_tool_from_directory(tool_dir: Path) -> StructuredTool:
    json_path = tool_dir / "tool.json"
    py_path = tool_dir / "tool.py"

    if not json_path.exists() or not py_path.exists():
        return None

    # 1. Read JSON manifest
    with open(json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # 2. Dynamically import run() fucntion from tools.py
    spec = importlib.util.spec_from_file_location(meta["name"], py_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    func = getattr(module, "run")
   

    # 3. Build dynamic Pydantic argument schema from parameters
    properties = meta.get("parameters", {}).get("properties", {})
    required_fields = meta.get("parameters", {}).get("required", [])

    fields = {}
    for prop_name, prop_data in properties.items():
        py_type = TYPE_MAPPING.get(prop_data.get("type"), str)
        desc = prop_data.get("description", "")
        default_val = ... if prop_name in required_fields else prop_data.get("default", None)
        fields[prop_name] = (py_type, Field(default=default_val, description=desc))
    
        # {
            # "a": (float, Field(..., description="First number")),
            # "b": (float, Field(..., description="Second number"))
        # }   

    # This creates a Pydantic model at runtime.
    args_schema = create_model(f"{meta['name']}_args", **fields)

    # 4. Enhance description with expected return format for the LLM
    returns_desc = ""
    if "returns" in meta and "properties" in meta["returns"]:
        return_keys = list(meta["returns"]["properties"].keys())
        returns_desc = f" Returns JSON with keys: {', '.join(return_keys)}."

    full_description = f"{meta['description']}{returns_desc}"

    # 5. Wrap inside StructuredTool what is a tool in langchain
    return StructuredTool(
        name=meta["name"],
        description=full_description,
        func=func,
        args_schema=args_schema
    )

def discover_registry_tools(registry_path: str = "registry/tools") -> list[StructuredTool]:
    """Scans registry folder and loads all available tools."""
    base_dir = Path(registry_path)
    loaded_tools = []
    
    if not base_dir.exists():
        return loaded_tools

    for item in sorted(base_dir.iterdir()):
        if item.is_dir():
            tool = load_tool_from_directory(item)
            if tool:
                loaded_tools.append(tool)
    # StructuredTools are stored in "Loaded tools"    
    return loaded_tools