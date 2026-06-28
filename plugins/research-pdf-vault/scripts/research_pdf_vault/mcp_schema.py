from __future__ import annotations

from typing import Final

from research_pdf_vault.mcp_types import JsonObject, ToolSpec

STRING_SCHEMA: Final[JsonObject] = {"type": "string"}
BOOLEAN_SCHEMA: Final[JsonObject] = {"type": "boolean"}
INTEGER_SCHEMA: Final[JsonObject] = {"type": "integer", "minimum": 1, "maximum": 50}
DECISION_SCHEMA: Final[JsonObject] = {
    "type": "string",
    "enum": ["approve", "reject", "defer", "quarantine"],
}


def object_schema(properties: JsonObject, required: list[str]) -> JsonObject:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


TOOL_SPECS: Final[tuple[ToolSpec, ...]] = (
    ToolSpec(
        name="get_manifest_summary",
        description="Summarize local manifest counts, lanes, review queue, and reports.",
        input_schema=object_schema({}, []),
    ),
    ToolSpec(
        name="search_papers",
        description="Search paper metadata and allowed local snippets without exposing Red full text.",
        input_schema=object_schema(
            {"query": STRING_SCHEMA, "limit": INTEGER_SCHEMA},
            ["query"],
        ),
    ),
    ToolSpec(
        name="get_paper",
        description="Read one paper record, instances, review state, artifacts, and permitted passages.",
        input_schema=object_schema(
            {"paper_id": STRING_SCHEMA, "include_full_text": BOOLEAN_SCHEMA},
            ["paper_id"],
        ),
    ),
    ToolSpec(
        name="list_review_queue",
        description="List queued non-Green review items from local review state.",
        input_schema=object_schema({"limit": INTEGER_SCHEMA}, []),
    ),
    ToolSpec(
        name="apply_review_decision",
        description="Apply a v1 review decision, writing only review queue and audit state.",
        input_schema=object_schema(
            {
                "identifier": STRING_SCHEMA,
                "decision": DECISION_SCHEMA,
                "actor": STRING_SCHEMA,
                "reason": STRING_SCHEMA,
                "timestamp": STRING_SCHEMA,
                "allow_sensitive": BOOLEAN_SCHEMA,
            },
            ["identifier", "decision", "actor", "reason", "timestamp"],
        ),
    ),
    ToolSpec(
        name="list_reports",
        description="List local worker report summaries.",
        input_schema=object_schema({}, []),
    ),
    ToolSpec(
        name="get_report",
        description="Read one local worker report summary by report_id.",
        input_schema=object_schema({"report_id": STRING_SCHEMA}, ["report_id"]),
    ),
)
