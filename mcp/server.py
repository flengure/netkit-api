#!/usr/bin/env python3
"""
netkit-api MCP stdio server

Exposes all network tools via MCP (Model Context Protocol).
Transport: JSON-RPC 2.0 over stdio (newline-delimited)
"""

import sys
import json
import os
from typing import Any, Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from executors import get_tool_registry
from target_validator import TargetValidator
from config_loader import load_config

JSONRPC = "2.0"

# Load config from file (if present) + environment variables
config = load_config()

# Target validation (lists are merged: file + env)
SCAN_WHITELIST = config.get_list("scan_whitelist", "SCAN_WHITELIST", [])
SCAN_BLACKLIST = config.get_list("scan_blacklist", "SCAN_BLACKLIST", [])
ALLOW_PRIVATE_IPS = config.get_bool("allow_private_ips", "ALLOW_PRIVATE_IPS", False)

target_validator = TargetValidator(
    whitelist=SCAN_WHITELIST or None,
    blacklist=SCAN_BLACKLIST or None,
    allow_private=ALLOW_PRIVATE_IPS
)

TOOL_REGISTRY = get_tool_registry(target_validator)

# MCP error codes
class MCPErrorCodes:
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    # Custom error codes
    TOOL_NOT_FOUND = -32001
    TOOL_UNAVAILABLE = -32002
    EXECUTION_ERROR = -32003
    PERMISSION_ERROR = -32004


def jr(id_: Any, result: Any = None, error: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create JSON-RPC response"""
    if error is not None:
        return {"jsonrpc": JSONRPC, "id": id_, "error": error}
    return {"jsonrpc": JSONRPC, "id": id_, "result": result}


def jerr(id_: Any, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create JSON-RPC error response"""
    error_obj = {"code": code, "message": message}
    if data:
        error_obj["data"] = data
    return jr(id_, error=error_obj)


def mcp_initialize(_params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP initialize request"""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": False}
        },
        "serverInfo": {
            "name": "netkit-api-mcp",
            "version": "1.0.0",
        }
    }


def mcp_tools_list(_params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tools/list request - return all available tools"""
    tools = []

    for name, executor in TOOL_REGISTRY.items():
        # Build input schema based on tool
        # Note: Either 'command' or 'args' must be provided (enforced by backend, not schema)
        # 'oneOf' removed for Zed compatibility - see issues/MCP_schema_compatibility_note.md
        input_schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": f"Command arguments as string (e.g., '{name} arg1 arg2'). Either 'command' or 'args' must be provided."
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command arguments as array. Either 'command' or 'args' must be provided."
                },
                "timeout": {
                    "type": "integer",
                    "description": f"Timeout in seconds (default: {executor.DEFAULT_TIMEOUT}, max: {executor.MAX_TIMEOUT})",
                    "default": executor.DEFAULT_TIMEOUT
                }
            }
        }

        # Add SSH-specific parameters
        if name == "ssh":
            input_schema["properties"].update({
                "host": {"type": "string", "description": "SSH host or alias"},
                "user": {"type": "string", "description": "SSH user (optional)"},
                "port": {"type": "integer", "description": "SSH port (optional)"},
                "ssh_dir": {"type": "string", "description": "Path to .ssh directory (optional)"},
                "strict_host_key_checking": {
                    "type": "string",
                    "enum": ["yes", "no", "accept-new"],
                    "description": "StrictHostKeyChecking option"
                },
                "proxy_jump": {"type": "string", "description": "ProxyJump host"},
                "allocate_tty": {"type": "boolean", "description": "Allocate TTY"},
            })

        tools.append({
            "name": name,
            "description": executor.DESCRIPTION or f"{name} - network/system tool",
            "inputSchema": input_schema,
        })

    return {"tools": tools}


def mcp_tools_call(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tool call requests"""
    name = params.get("name")
    arguments = params.get("arguments") or {}

    # Check if tool exists
    if name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {name}")

    executor = TOOL_REGISTRY[name]

    # Check if tool is available
    if not executor.is_available():
        raise RuntimeError(f"Tool '{name}' is not installed or not available")

    # Execute tool
    try:
        result = executor.execute(arguments)

        # Format output for MCP
        output_text = f"{name} execution completed\n\n"
        output_text += f"Exit code: {result['exit_code']}\n"
        output_text += f"Duration: {result['duration_seconds']}s\n\n"

        if result['stdout']:
            output_text += f"=== Output ===\n{result['stdout']}\n"

        if result['stderr']:
            output_text += f"\n=== Errors ===\n{result['stderr']}\n"

        return {
            "content": [
                {
                    "type": "text",
                    "text": output_text
                }
            ],
            "isError": result['exit_code'] != 0
        }

    except PermissionError as e:
        raise PermissionError(f"Permission denied: {str(e)}")
    except ValueError as e:
        raise ValueError(f"Invalid parameters: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Execution failed: {str(e)}")


def handle(req: Dict[str, Any]) -> Dict[str, Any]:
    """Handle incoming JSON-RPC requests"""
    if not isinstance(req, dict) or req.get("jsonrpc") != JSONRPC:
        req_id = req.get("id") if isinstance(req, dict) else 0
        if req_id is None:
            req_id = 0
        return jerr(req_id, MCPErrorCodes.INVALID_REQUEST, "Invalid Request")

    method = req.get("method")
    _id = req.get("id")
    if _id is None:
        _id = 0
    params = req.get("params") or {}

    try:
        if method == "initialize":
            return jr(_id, mcp_initialize(params))
        elif method == "tools/list":
            return jr(_id, mcp_tools_list(params))
        elif method == "tools/call":
            return jr(_id, mcp_tools_call(params))
        else:
            return jerr(_id, MCPErrorCodes.METHOD_NOT_FOUND, f"Method not found: {method}")

    except ValueError as e:
        return jerr(_id, MCPErrorCodes.INVALID_PARAMS, str(e))

    except PermissionError as e:
        return jerr(_id, MCPErrorCodes.PERMISSION_ERROR, str(e))

    except RuntimeError as e:
        return jerr(_id, MCPErrorCodes.TOOL_UNAVAILABLE, str(e))

    except Exception as e:
        return jerr(_id, MCPErrorCodes.INTERNAL_ERROR, f"Internal server error: {str(e)}")


def main():
    """Main MCP server loop - read JSON-RPC requests from stdin and respond"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            error_resp = {
                "jsonrpc": JSONRPC,
                "error": {
                    "code": MCPErrorCodes.PARSE_ERROR,
                    "message": "Parse error: Invalid JSON"
                }
            }
            print(json.dumps(error_resp), flush=True)
            continue

        resp = handle(req)
        print(json.dumps(resp, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
