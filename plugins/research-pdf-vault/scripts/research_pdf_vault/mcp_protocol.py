from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TextIO

from research_pdf_vault.mcp_tools import McpToolRunner
from research_pdf_vault.mcp_types import (
    JsonObject,
    JsonValue,
    McpToolError,
    is_json_object,
    string_arg,
)


@dataclass(frozen=True, slots=True)
class JsonRpcRequest:
    request_id: JsonValue
    method: str
    params: JsonObject


def run_stdio_server(
    runner: McpToolRunner,
    input_stream: TextIO,
    output_stream: TextIO,
) -> None:
    for line in input_stream:
        if line.strip():
            output_stream.write(handle_json_line(runner, line) + "\n")
            output_stream.flush()


def handle_json_line(runner: McpToolRunner, line: str) -> str:
    try:
        raw_request = json.loads(line)
    except json.JSONDecodeError as error:
        return json.dumps(_error_response(None, -32700, f"parse error: {error.msg}"))
    if not is_json_object(raw_request):
        return json.dumps(_error_response(None, -32600, "request must be an object"))
    request_id = raw_request.get("id")
    try:
        request = _parse_request(raw_request)
        return json.dumps(_result_response(request.request_id, _dispatch(runner, request)))
    except McpToolError as error:
        return json.dumps(_error_response(request_id, -32602, str(error)))


def _parse_request(raw_request: JsonObject) -> JsonRpcRequest:
    method = string_arg(raw_request, "method")
    raw_params = raw_request.get("params")
    if raw_params is None:
        params: JsonObject = {}
    elif is_json_object(raw_params):
        params = raw_params
    else:
        raise McpToolError("params must be an object")
    return JsonRpcRequest(
        request_id=raw_request.get("id"),
        method=method,
        params=params,
    )


def _dispatch(runner: McpToolRunner, request: JsonRpcRequest) -> JsonObject:
    if request.method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "research-pdf-vault", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        }
    if request.method == "tools/list":
        return {"tools": runner.tool_specs()}
    if request.method == "tools/call":
        return _tool_call(runner, request.params)
    if request.method == "ping":
        return {}
    raise McpToolError(f"unsupported method: {request.method}")


def _tool_call(runner: McpToolRunner, params: JsonObject) -> JsonObject:
    name = string_arg(params, "name")
    raw_arguments = params.get("arguments")
    if raw_arguments is None:
        arguments: JsonObject = {}
    elif is_json_object(raw_arguments):
        arguments = raw_arguments
    else:
        raise McpToolError("arguments must be an object")
    return runner.call_tool(name, arguments)


def _result_response(request_id: JsonValue, result: JsonObject) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(
    request_id: JsonValue,
    code: int,
    message: str,
) -> JsonObject:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
