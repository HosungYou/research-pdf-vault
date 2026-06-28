from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from research_pdf_vault.config import ConfigLoadRequest, VaultRuntimeConfig, load_config
from research_pdf_vault.mcp_db import open_read_connection
from research_pdf_vault.mcp_manifest import get_manifest_summary, list_review_queue
from research_pdf_vault.mcp_papers import get_paper, search_papers
from research_pdf_vault.mcp_review import apply_review_decision
from research_pdf_vault.mcp_schema import TOOL_SPECS
from research_pdf_vault.mcp_types import JsonObject, McpToolError, string_arg
from research_pdf_vault.reports import get_worker_report, list_worker_reports


@dataclass(frozen=True, slots=True)
class McpToolRunner:
    config: VaultRuntimeConfig

    @classmethod
    def from_config_path(cls, config_path: Path | None) -> McpToolRunner:
        return cls(load_config(ConfigLoadRequest(config_path=config_path)))

    def tool_specs(self) -> list[JsonObject]:
        return [spec.to_json() for spec in TOOL_SPECS]

    def call_tool(self, name: str, arguments: JsonObject) -> JsonObject:
        if name == "get_manifest_summary":
            return get_manifest_summary(self.config)
        if name == "search_papers":
            return search_papers(self.config, arguments)
        if name == "get_paper":
            return get_paper(self.config, arguments)
        if name == "list_review_queue":
            return list_review_queue(self.config, arguments)
        if name == "apply_review_decision":
            return apply_review_decision(self.config, arguments)
        if name == "list_reports":
            return self.list_reports()
        if name == "get_report":
            return self.get_report(arguments)
        raise McpToolError(f"unknown MCP tool: {name}")

    def list_reports(self) -> JsonObject:
        connection = open_read_connection(self.config)
        if connection is None:
            return {"reports": []}
        with closing(connection):
            return {"reports": list_worker_reports(connection)}

    def get_report(self, arguments: JsonObject) -> JsonObject:
        report_id = _report_id(arguments)
        connection = open_read_connection(self.config)
        if connection is None:
            return {"status": "missing", "report_id": report_id}
        with closing(connection):
            report = get_worker_report(connection, report_id)
            if report is None:
                return {"status": "missing", "report_id": report_id}
            return {"status": "ok", "report": report}


def _report_id(arguments: JsonObject) -> str:
    return string_arg(arguments, "report_id")
