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
VALID_STATUSES = ["pending", "researching", "validated", "integrated", "failed", "rejected_contradiction"]


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


def _check_contradiction(proposed: dict, kg: dict) -> dict | None:
    """
    Check if a proposed acquired node contradicts any core node.

    Returns None if OK to add, or a rejection dict if conflicting:
    {
        "reason": "core_conflict" | "antipattern_forbidden",
        "conflicting_node_id": str,
        "conflicting_label": str,
        "details": str
    }
    """
    from aec_concept import tokenize, dice_bigram

    subject = proposed.get("subject", "")
    predicate = proposed.get("predicate", "").lower()
    obj = str(proposed.get("object", ""))

    if not subject:
        return None

    subject_tokens = tokenize(subject)
    nodes = kg.get("@graph", [])

    for node in nodes:
        origin = node.get("aether:origin", "")
        node_id = node.get("@id", "")
        label = node.get("rdfs:label", "")
        node_type = node.get("@type", "")

        if not label:
            continue

        # Calculate subject similarity using Dice bigram
        dice = dice_bigram(subject, label)

        # Check 1: Core node with same subject (Dice > 0.6)
        if origin == "core" and dice > 0.6:
            # Check for predicate conflict: same predicate, different object
            for key, value in node.items():
                if key.startswith("@") or key.startswith("aether:") or key == "rdfs:label":
                    continue
                # Normalize predicate comparison
                key_normalized = key.lower().replace("_", " ").replace("-", " ")
                pred_normalized = predicate.replace("_", " ").replace("-", " ")

                if key_normalized == pred_normalized or dice_bigram(key_normalized, pred_normalized) > 0.7:
                    # Same predicate - check if objects conflict
                    existing_obj = str(value).lower().strip()
                    proposed_obj = obj.lower().strip()

                    if existing_obj != proposed_obj and existing_obj and proposed_obj:
                        return {
                            "reason": "core_conflict",
                            "conflicting_node_id": node_id,
                            "conflicting_label": label,
                            "details": f"Core node has {key}={value}, proposed {predicate}={obj}"
                        }

        # Check 2: AntiPattern nodes - can't learn what your rules forbid
        if "AntiPattern" in node_type:
            label_tokens = tokenize(label)

            # Check if proposed subject matches antipattern (Dice > 0.6 OR significant token overlap)
            antipattern_dice = dice_bigram(subject, label)
            subject_overlap = subject_tokens & label_tokens
            subject_coverage = len(subject_overlap) / len(subject_tokens) if subject_tokens else 0

            if antipattern_dice > 0.6 or subject_coverage >= 0.5:
                return {
                    "reason": "antipattern_forbidden",
                    "conflicting_node_id": node_id,
                    "conflicting_label": label,
                    "details": f"Cannot learn '{subject}' - matches antipattern '{label}'"
                }

            # Also check if proposed object matches antipattern terms
            obj_tokens = tokenize(obj)
            obj_dice = dice_bigram(obj, label)
            obj_overlap = obj_tokens & label_tokens
            obj_coverage = len(obj_overlap) / len(obj_tokens) if obj_tokens else 0

            if obj_dice > 0.5 or obj_coverage >= 0.5:
                return {
                    "reason": "antipattern_forbidden",
                    "conflicting_node_id": node_id,
                    "conflicting_label": label,
                    "details": f"Cannot learn object '{obj}' - matches antipattern '{label}'"
                }

    return None


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
        "triples_rejected": [],
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
    triples_rejected = []

    for t in triples:
        if not all(k in t for k in ["subject", "predicate", "object"]):
            continue

        # Contradiction gate: check if proposed triple conflicts with core nodes
        contradiction = _check_contradiction(t, kg)
        if contradiction:
            triples_rejected.append({
                "triple": t,
                "status": "rejected_contradiction",
                "reason": contradiction["reason"],
                "conflicting_node_id": contradiction["conflicting_node_id"],
                "conflicting_label": contradiction["conflicting_label"],
                "details": contradiction["details"],
            })
            continue  # Skip this triple - core has veto

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
    result["triples_rejected"] = triples_rejected

    # 6. RE-EVALUATE: Run AEC on original response with updated KG
    kg = load_kg(kg_path)  # Reload to get fresh data
    all_nodes = get_nodes(kg)
    original_response = record.get("response", "")

    new_aec = aec_verify(original_response, all_nodes, threshold)
    result["new_score"] = new_aec["score"]

    # Build status metadata including any rejections
    status_meta = {
        "new_score": new_aec["score"],
        "triples_added": triples_added,
    }
    if triples_rejected:
        status_meta["triples_rejected"] = len(triples_rejected)
        status_meta["rejection_details"] = triples_rejected

    if new_aec["passed"]:
        result["status"] = "integrated"
        update_status(capsule_path, record_id, "integrated", status_meta)
    else:
        result["status"] = "failed"
        result["reason"] = "still_below_threshold"
        status_meta["reason"] = "still_below_threshold"
        update_status(capsule_path, record_id, "failed", status_meta)

    return result


def get_oldest_pending(capsule_path: str | Path) -> dict | None:
    """Return the oldest pending record, or None if none pending."""
    pending = get_pending(capsule_path)
    if not pending:
        return None
    # Sort by timestamp (oldest first)
    pending.sort(key=lambda r: r.get("timestamp", ""))
    return pending[0]


def refine_session(capsule_path: str | Path, n: int = 50, auto_queue: bool = False) -> dict:
    """
    Analyze education queue and surface KG improvement candidates.

    Separates persona gaps (not KG-groundable) from factual gaps,
    clusters factual gaps by subject, and identifies unresolved failures.

    Args:
        capsule_path: Path to capsule folder
        n: Number of most recent records to analyze (default 50)
        auto_queue: If True, auto-queue high-priority candidates

    Returns:
        Result dict with candidates, unresolved failures, and summary
    """
    capsule_path = Path(capsule_path)

    # Initialize result
    result = {
        "capsule_path": str(capsule_path),
        "analyzed": 0,
        "timestamp": datetime.now().isoformat(),
        "persona_gaps_filtered": 0,
        "factual_gaps_found": 0,
        "candidates": [],
        "unresolved_failures": [],
        "summary": "",
        "auto_queued": 0,
    }

    # Step 1: Load records
    queue = _load_queue(capsule_path)
    if not queue:
        result["summary"] = "No records in education queue. Run some queries to populate it."
        return result

    # Sort by timestamp descending, take n most recent
    queue.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    records = queue[:max(1, n)]
    result["analyzed"] = len(records)

    # Persona markers to filter out
    PERSONA_MARKERS = {
        "i", "we", "my", "our", "you", "me",
        "think", "feel", "believe", "smile", "love", "hate", "say", "told",
        "called", "like", "sweet", "wonderful", "beautiful", "great", "best",
        "joke", "dream", "happy", "sad", "amazing", "incredible", "absolutely"
    }

    # Factual relationship markers
    FACTUAL_MARKERS = {
        "acquired", "founded", "paid", "born", "invested", "cost", "earned",
        "purchased", "built", "sold", "grew", "generated", "returned", "bought",
        "worth", "valued", "priced", "totaled", "reached", "hit"
    }

    def is_persona_gap(text: str) -> bool:
        """Filter gap as persona (not KG-groundable)."""
        text_lower = text.lower()
        words = text_lower.split()

        # Too short
        if len(words) < 8:
            return True

        # Contains persona markers
        if any(marker in words for marker in PERSONA_MARKERS):
            return True

        # No numbers, years, or dollar amounts
        has_number = bool(re.search(r'\d', text))
        has_dollar = '$' in text

        # No capitalized proper nouns (excluding first word)
        words_original = text.split()
        has_proper_noun = any(
            w[0].isupper() and w.isalpha() and i > 0
            for i, w in enumerate(words_original)
        )

        # If no verifiable content, it's persona
        if not has_number and not has_dollar and not has_proper_noun:
            return True

        return False

    def is_factual_gap(text: str) -> bool:
        """Identify gap as factual (potentially KG-groundable)."""
        text_lower = text.lower()

        # Has number, year, or dollar amount
        if re.search(r'\$[\d,]+|\d{4}|\d+\s*(million|billion|percent|%)', text_lower):
            return True

        # Has factual relationship marker
        if any(marker in text_lower for marker in FACTUAL_MARKERS):
            return True

        # Has capitalized entity (not at start)
        words = text.split()
        if any(w[0].isupper() and w.isalpha() and i > 0 for i, w in enumerate(words)):
            # Also has some concrete content
            if re.search(r'\d', text) or any(m in text_lower for m in FACTUAL_MARKERS):
                return True

        return False

    def extract_subject(text: str) -> str:
        """Extract subject from gap text (first capitalized entity or first 3 meaningful words)."""
        # Skip common sentence starters and pronouns
        skip_words = {
            "The", "This", "That", "These", "Those", "It", "He", "She", "They", "We", "You", "I",
            "His", "Her", "Its", "Their", "Our", "Your", "My", "And", "But", "Or", "So", "If",
            "Now", "Well", "Back", "For", "In", "On", "At", "To", "From", "With", "By",
            "What", "When", "Where", "Why", "How", "Here", "There", "Some", "All", "Any",
            "Just", "Even", "Only", "Best", "Most", "Very", "Really", "Actually"
        }

        # Find capitalized word sequences that are proper nouns (not skip words)
        for match in re.finditer(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text):
            candidate = match.group(1)
            first_word = candidate.split()[0]
            if first_word not in skip_words:
                return candidate

        # Fallback: first 3 content words (skip articles/prepositions)
        words = text.split()
        content_words = [w for w in words if w.lower() not in {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "to", "of", "in", "for", "on", "with", "at", "by", "from", "and", "or", "but"
        }][:3]
        return " ".join(content_words) if content_words else " ".join(words[:3])

    # Step 2 & 3: Separate persona from factual gaps and cluster by subject
    subject_clusters = {}  # subject -> {gap_texts: set, records: set, statuses: list}

    for record in records:
        gaps = record.get("gaps", [])
        record_id = record.get("id", "unknown")
        status = record.get("status", "unknown")

        for gap in gaps:
            gap_text = gap.get("text", "")
            if not gap_text:
                continue

            if is_persona_gap(gap_text):
                result["persona_gaps_filtered"] += 1
                continue

            if is_factual_gap(gap_text):
                result["factual_gaps_found"] += 1
                subject = extract_subject(gap_text)

                if subject not in subject_clusters:
                    subject_clusters[subject] = {
                        "gap_texts": set(),
                        "records": set(),
                        "statuses": []
                    }

                subject_clusters[subject]["gap_texts"].add(gap_text)
                subject_clusters[subject]["records"].add(record_id)
                subject_clusters[subject]["statuses"].append(status)

    # Step 4: Score candidates
    candidates = []
    for subject, data in subject_clusters.items():
        frequency = len(data["records"])
        status_breakdown = {}
        for s in data["statuses"]:
            status_breakdown[s] = status_breakdown.get(s, 0) + 1

        # Determine priority
        has_failed = "failed" in status_breakdown
        if frequency >= 3 or has_failed:
            priority = "high"
        elif frequency == 2:
            priority = "medium"
        else:
            priority = "low"

        candidates.append({
            "subject": subject,
            "frequency": frequency,
            "priority": priority,
            "gap_texts": list(data["gap_texts"]),
            "records_affected": list(data["records"]),
            "status_breakdown": status_breakdown,
        })

    # Sort by priority (high > medium > low) then by frequency descending
    priority_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda c: (priority_order[c["priority"]], -c["frequency"]))
    result["candidates"] = candidates

    # Step 5: Identify unresolved failures
    for record in records:
        if record.get("status") == "failed" and record.get("reason") == "still_below_threshold":
            result["unresolved_failures"].append({
                "id": record.get("id", ""),
                "query": record.get("query", ""),
                "aec_score": record.get("aec_score", 0),
                "gaps": record.get("gaps", []),
                "reason": record.get("reason", ""),
            })

    # Step 6: Build summary
    high_priority_count = len([c for c in candidates if c["priority"] == "high"])
    unresolved_count = len(result["unresolved_failures"])

    if result["analyzed"] == 0:
        result["summary"] = "No records in education queue. Run some queries to populate it."
    elif result["factual_gaps_found"] == 0:
        result["summary"] = (
            f"Analyzed {result['analyzed']} records. "
            f"All {result['persona_gaps_filtered']} gap statements were persona-style and not KG-groundable."
        )
    else:
        result["summary"] = (
            f"Analyzed {result['analyzed']} records. Found {len(candidates)} recurring knowledge gap subjects "
            f"({result['persona_gaps_filtered']} persona statements filtered). "
            f"{high_priority_count} high-priority candidates identified. "
            f"{unresolved_count} records failed education and remain unresolved."
        )

    # Step 7: Auto-queue high priority candidates
    if auto_queue:
        for candidate in candidates:
            if candidate["priority"] == "high":
                aec_result = {
                    "score": 0.0,
                    "threshold": 0.8,
                    "passed": False,
                    "gaps": [{"text": t, "reason": "refine_candidate"} for t in candidate["gap_texts"]]
                }
                queue_failure(
                    capsule_path,
                    query=f"Knowledge gap: {candidate['subject']}",
                    response=f"Agent produced ungrounded claims about {candidate['subject']}",
                    aec_result=aec_result
                )
                result["auto_queued"] += 1

    return result


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
