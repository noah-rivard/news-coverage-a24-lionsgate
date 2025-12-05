import json
from pathlib import Path

from news_coverage.cli import _to_plain, _write_output
from news_coverage.workflow import (
    ClassificationResult,
    IngestResult,
    PipelineResult,
    SummaryResult,
)


def _make_result(path: Path) -> PipelineResult:
    classification = ClassificationResult(
        category="Content, Deals & Distribution -> TV -> Development",
        section="Content / Deals / Distribution",
        subheading="Development",
        confidence=0.91,
        company="A24",
        quarter="2025 Q1",
    )
    summary = SummaryResult(bullets=["First point", "Second point"])
    ingest = IngestResult(stored_path=path, duplicate_of=None)
    return PipelineResult(
        markdown="**Title**\n- First point",
        classification=classification,
        summary=summary,
        ingest=ingest,
    )


def test_to_plain_serializes_paths_and_dataclasses(tmp_path):
    stored = tmp_path / "data" / "ingest" / "A24" / "2025 Q1.jsonl"
    result = _make_result(stored)

    payload = _to_plain(result)

    assert isinstance(payload, dict)
    assert payload["ingest"]["stored_path"] == str(stored)
    # Ensure the payload can be dumped to JSON without raising.
    json.dumps(payload)


def test_write_output_json(tmp_path):
    out_file = tmp_path / "result.json"
    payload = _to_plain(_make_result(tmp_path / "data.jsonl"))

    _write_output(out_file, markdown="unused", json_payload=payload)

    written = json.loads(out_file.read_text(encoding="utf-8"))
    assert written["classification"]["company"] == "A24"
    assert written["ingest"]["duplicate_of"] is None
