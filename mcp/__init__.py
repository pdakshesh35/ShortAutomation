from typing import Callable, Any, Dict

Tool = Callable[..., Any]
TOOL_REGISTRY: Dict[str, Tool] = {}

def tool(name: str) -> Callable[[Tool], Tool]:
    """Decorator to register a function as an MCP tool."""
    def decorator(func: Tool) -> Tool:
        TOOL_REGISTRY[name] = func
        return func
    return decorator
