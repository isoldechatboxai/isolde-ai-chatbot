# app/services/tool_registry.py

import inspect
import functools
from typing import Callable, Dict, Any, List, Optional
from flask import current_app

class ToolRegistry:
    """
    Registry for managing executable tools, functions, and utilities
    that autonomous AI agents can discover, inspect, and invoke safely.
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        """
        Decorator to register a python function as an executable agent tool.
        """
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or func.__doc__ or "No description provided."
            
            # Inspect signature to understand parameters
            sig = inspect.signature(func)
            parameters = {}
            for param_name, param in sig.parameters.items():
                parameters[param_name] = {
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                    "required": param.default == inspect.Parameter.empty
                }

            self._tools[tool_name] = {
                "name": tool_name,
                "description": tool_desc.strip(),
                "function": func,
                "parameters": parameters
            }

            if current_app:
                current_app.logger.info(f"[ToolRegistry] Registered tool: '{tool_name}'")

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        """Retrieves the executable function for a given tool name."""
        tool_data = self._tools.get(name)
        return tool_data.get("function") if tool_data else None

    def list_tools(self) -> List[Dict[str, Any]]:
        """Returns metadata for all registered tools (useful for LLM function calling prompts)."""
        return [
            {
                "name": info["name"],
                "description": info["description"],
                "parameters": info["parameters"]
            }
            for info in self._tools.values()
        ]

    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Safely executes a registered tool with provided keyword arguments."""
        tool_func = self.get_tool(name)
        if not tool_func:
            return {"success": False, "error": f"Tool '{name}' not found in registry."}

        try:
            result = tool_func(**args)
            if current_app:
                current_app.logger.info(f"[ToolRegistry] Successfully executed tool: '{name}'")
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[ToolRegistry] Error executing tool '{name}': {str(e)}")
            return {"success": False, "result": None, "error": str(e)}

# Singleton instance for application-wide use
tool_registry = ToolRegistry()