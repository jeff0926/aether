"""
Education - AEC failure queue for capsule self-improvement.
Captures failed prompt-response pairs for later research and integration.
Includes self-education loop: research, validate, integrate.
"""

import json
import hashlib
import re
from pathlib import Path
from datetime import datetime

QUEUE_FILE = "education-queue.json"
VALID_STATUSES = ["pending", "researching", "validated", "integrated", "failed"]


def _queue_path(capsule_path: str | Path) -> Path:
    """Get path to education queue file."""
    return Path(capsule_path) / QUEUE_FILE


def _load_queue(capsule_path: str | Path) -> list[dict]:
    """Load queue from file, return empty list if missing."""
    path = _queue_path(capsule_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_queue(capsule_path: str | Path, queue: list[dict]) -> None:
    """Save queue to file."""
    path = _queue_path(capsule_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def queue_failure(capsule_path: str | Path, query: str, response: str, aec_result: dict) -> dict:
    """
    Queue a failed AEC result for later education.
    Returns the record that was written.
    """
    timestamp = datetime.now().isoformat()
    raw = f"{timestamp}:{query[:50]}:{response[:50]}"
    hash8 = hashlib.sha256(raw.encode()).hexdigest()[:8]

    record = {
        "id": f"{timestamp[:19].replace(':', '-')}-{hash8}",
        "timestamp": timestamp,
        "query": query,
        "response": response,
        "aec_score": aec_result.get("score", 0),
        "threshold": aec_result.get("threshold", 0.8),
        "gaps": aec_result.get("gaps", []),
        "status": "pending",
    }

    queue = _load_queue(capsule_path)
    queue.append(record)
    _save_queue(capsule_path, queue)

    return record


def get_queue(capsule_path: str | Path) -> list[dict]:
    """Read and return all records from education queue."""
    return _load_queue(capsule_path)


def get_pending(capsule_path: str | Path) -> list[dict]:
    """Return only records with status 'pending'."""
    return [r for r in _load_queue(capsule_path) if r.get("status") == "pending"]


def update_status(capsule_path: str | Path, record_id: str, status: str, metadata: dict = None) -> bool:
    """
    Update a record's status and optionally merge metadata.
    Returns True if record found and updated, False otherwise.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")

    queue = _load_queue(capsule_path)
    for record in queue:
        if record.get("id") == record_id:
            record["status"] = status
            record["status_updated"] = datetime.now().isoformat()
            if metadata:
                record.update(metadata)
            _save_queue(capsule_path, queue)
            return True
    return False


def queue_stats(capsule_path: str | Path) -> dict:
    """Return counts by status."""
    queue = _load_queue(capsule_path)
    stats = {"total": len(queue)}
    for status in VALID_STATUSES:
        stats[status] = len([r for r in queue if r.get("status") == status])
    return stats


def _parse_json_response(text: str) -> list[dict]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code blocks
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Try to find JSON array in the text
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        text = match.group(0)

    return json.loads(text)


def _build_research_prompt(gaps: list[dict]) -> str:
    """Build research prompt for ungrounded statements."""
    statements = "\n".join(f"{i+1}. {g.get('text', '')}" for i, g in enumerate(gaps))

    return f"""The following statements could not be verified against the agent's knowledge graph. For each statement, provide the factual information as structured data.

Statements:
{statements}

For each statement, respond with:
- subject: the main entity
- predicate: the relationship (e.g., BORN_IN, COST, OCCURRED_IN, LED_BY, FOUNDED)
- object: the value or target entity
- object_type: Person, Location, Event, Number, Date, Concept

Respond ONLY in JSON array format. No prose. Example:
[
  {{"subject": "Thomas Jefferson", "predicate": "BORN_IN", "object": "1743", "object_type": "Date"}}
]"""


def educate(capsule_path: str | Path, record_id: str, llm_fn: callable) -> dict:
    """
    Self-education loop: research gaps, validate, integrate knowledge.

    Steps:
    1. Load failure record, verify pending, update to researching
    2. Extract gap statements
    3. Research via LLM to get structured triples
    4. Validate research output through AEC
    5. Integrate validated triples into KG
    6. Re-evaluate original response with updated KG
    7. Return results
    """
    # Lazy imports to avoid circular dependency
    from aether import get_required_files
    from kg import load_kg, add_knowledge, save_kg, get_nodes
    from aec import verify as aec_verify

    capsule_path = Path(capsule_path)
    result = {
        "record_id": record_id,
        "status": "failed",
        "original_score": 0.0,
        "new_score": 0.0,
        "triples_added": 0,
        "research_tokens": {"in": 0, "out": 0},
    }

    # 1. LOAD: Get the failure record
    queue = _load_queue(capsule_path)
    record = next((r for r in queue if r.get("id") == record_id), None)

    if not record:
        result["reason"] = "record_not_found"
        return result

    if record.get("status") != "pending":
        result["reason"] = f"invalid_status:{record.get('status')}"
        return result

    result["original_score"] = record.get("aec_score", 0.0)
    threshold = record.get("threshold", 0.8)

    # Update status to researching
    update_status(capsule_path, record_id, "researching")

    # 2. EXTRACT GAPS
    gaps = record.get("gaps", [])
    if not gaps:
        update_status(capsule_path, record_id, "failed", {"reason": "no_gaps"})
        result["reason"] = "no_gaps"
        return result

    # 3. RESEARCH: Call LLM for structured facts
    prompt = _build_research_prompt(gaps)
    llm_result = llm_fn(prompt)

    # Handle dict or string response
    if isinstance(llm_result, dict):
        research_text = llm_result.get("text", "")
        result["research_tokens"]["in"] = llm_result.get("tokens_in", 0)
        result["research_tokens"]["out"] = llm_result.get("tokens_out", 0)
    else:
        research_text = str(llm_result)

    # Parse JSON response
    try:
        triples = _parse_json_response(research_text)
        if not isinstance(triples, list):
            raise ValueError("Response is not a list")
    except (json.JSONDecodeError, ValueError) as e:
        update_status(capsule_path, record_id, "failed",
                      {"reason": "research_parse_error", "error": str(e), "raw_response": research_text[:500]})
        result["reason"] = "research_parse_error"
        return result

    if not triples:
        update_status(capsule_path, record_id, "failed", {"reason": "no_triples_returned"})
        result["reason"] = "no_triples_returned"
        return result

    # 4. VALIDATE: Check research output is internally consistent
    # Build test nodes from triples for AEC validation
    test_nodes = []
    for t in triples:
        if not all(k in t for k in ["subject", "predicate", "object"]):
            continue
        test_nodes.append({
            "@id": f"research:{t['subject'].replace(' ', '_').lower()}",
            "rdfs:label": t["subject"],
            t["predicate"].lower(): t["object"],
        })

    # Construct test statement from research
    test_statements = ". ".join(
        f"{t.get('subject', '?')} {t.get('predicate', '?').replace('_', ' ').lower()} {t.get('object', '?')}"
        for t in triples if all(k in t for k in ["subject", "predicate", "object"])
    )

    if test_nodes:
        validation = aec_verify(test_statements, test_nodes, threshold=0.5)
        if not validation["passed"] and validation["score"] < 0.5:
            update_status(capsule_path, record_id, "failed",
                          {"reason": "research_validation_failed", "validation_score": validation["score"]})
            result["reason"] = "research_validation_failed"
            return result

    # 5. INTEGRATE: Add validated triples to KG
    files = get_required_files(capsule_path.name)
    kg_path = capsule_path / files["kg"]
    kg = load_kg(kg_path)

    triples_added = 0
    for t in triples:
        if not all(k in t for k in ["subject", "predicate", "object"]):
            continue
        kg = add_knowledge(kg, {
            "subject": t["subject"],
            "predicate": t["predicate"].lower(),
            "object": t["object"],
            "confidence": 0.8,
            "aec_trigger": record_id,
        }, origin="acquired")
        triples_added += 1

    save_kg(kg, kg_path)
    result["triples_added"] = triples_added

    # 6. RE-EVALUATE: Run AEC on original response with updated KG
    kg = load_kg(kg_path)  # Reload to get fresh data
    all_nodes = get_nodes(kg)
    original_response = record.get("response", "")

    new_aec = aec_verify(original_response, all_nodes, threshold)
    result["new_score"] = new_aec["score"]

    if new_aec["passed"]:
        result["status"] = "integrated"
        update_status(capsule_path, record_id, "integrated", {
            "new_score": new_aec["score"],
            "triples_added": triples_added,
        })
    else:
        result["status"] = "failed"
        result["reason"] = "still_below_threshold"
        update_status(capsule_path, record_id, "failed", {
            "reason": "still_below_threshold",
            "new_score": new_aec["score"],
            "triples_added": triples_added,
        })

    return result


def get_oldest_pending(capsule_path: str | Path) -> dict | None:
    """Return the oldest pending record, or None if none pending."""
    pending = get_pending(capsule_path)
    if not pending:
        return None
    # Sort by timestamp (oldest first)
    pending.sort(key=lambda r: r.get("timestamp", ""))
    return pending[0]


if __name__ == "__main__":
    import tempfile
    import shutil

    # Create temp capsule folder
    with tempfile.TemporaryDirectory() as tmp:
        capsule = Path(tmp) / "test-capsule"
        capsule.mkdir()

        print("Testing education queue...")

        # Test queue_failure
        aec_result = {
            "score": 0.4,
            "threshold": 0.8,
            "passed": False,
            "gaps": [{"text": "Wrong date mentioned", "reason": "values_not_in_kg"}],
        }
        record = queue_failure(capsule, "When was Jefferson born?", "Jefferson was born in 1750.", aec_result)
        print(f"Queued: {record['id']}")
        assert record["status"] == "pending"
        assert record["aec_score"] == 0.4

        # Test get_queue
        queue = get_queue(capsule)
        assert len(queue) == 1
        print(f"Queue size: {len(queue)}")

        # Test get_pending
        pending = get_pending(capsule)
        assert len(pending) == 1
        print(f"Pending: {len(pending)}")

        # Test update_status
        success = update_status(capsule, record["id"], "researching", {"research_started": True})
        assert success
        print(f"Updated status: researching")

        # Verify status change
        queue = get_queue(capsule)
        assert queue[0]["status"] == "researching"
        assert queue[0].get("research_started") == True

        # Test queue_stats
        stats = queue_stats(capsule)
        print(f"Stats: {stats}")
        assert stats["total"] == 1
        assert stats["researching"] == 1
        assert stats["pending"] == 0

        # Add another failure
        queue_failure(capsule, "Second query", "Second response", aec_result)
        stats = queue_stats(capsule)
        assert stats["total"] == 2
        assert stats["pending"] == 1
        print(f"Final stats: {stats}")

        # Verify queue file exists
        assert (capsule / QUEUE_FILE).exists()
        print(f"Queue file created: {QUEUE_FILE}")

        print("\nAll tests passed!")
