"""Create the checked-in deterministic fake responses from the synthetic eval set."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATASET = ROOT / "data" / "evals" / "v1.jsonl"
OUTPUT = ROOT / "data" / "fixtures" / "good-results.jsonl"
DEFAULT_REVISIONS = {
    "travel-policy": "11111111-1111-4111-8111-222222222222",
    "security-policy": "22222222-2222-4222-8222-222222222222",
    "remote-work": "55555555-5555-4555-8555-555555555555",
    "benefits-policy": "66666666-6666-4666-8666-666666666666",
}


def main() -> None:
    records: list[str] = []
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        if case["expected_status"] == "abstained":
            result = {
                "status": "abstained",
                "answer": None,
                "context": [],
                "citations": [],
                "index_version": "fake-projection-v1",
            }
        else:
            source_id = case["expected_source_ids"][0]
            revision_id = (case.get("expected_revision_ids") or [DEFAULT_REVISIONS[source_id]])[0]
            chunk_id = f"{case['case_id']}-chunk"
            text = ". ".join(case["required_facts"])
            reference = {
                "source_id": source_id,
                "revision_id": revision_id,
                "chunk_id": chunk_id,
                "locator": {"case_id": case["case_id"], "paragraph": 1},
            }
            result = {
                "status": "answered",
                "answer": text,
                "context": [{"text": text, "reference": reference}],
                "citations": [reference],
                "index_version": "fake-projection-v1",
            }
        record = {
            "workspace_id": case["workspace_id"],
            "question": case["question"],
            "result": result,
        }
        records.append(json.dumps(record, ensure_ascii=False))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(records) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
