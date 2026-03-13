"""
Habitat - Capsule registry with message routing.
Where capsules live, discover each other, and exchange signals.
Includes query-to-capsule orchestration.
"""

import json
from pathlib import Path
from datetime import datetime


class Habitat:
    """
    In-memory registry for capsules with topic-based routing.
    Not async - just lookup and logging.
    """

    def __init__(self):
        self._registry: dict[str, dict] = {}  # capsule_id -> metadata
        self._log: list[dict] = []

    def register(self, capsule_id: str, metadata: dict) -> None:
        """Register a capsule with its metadata."""
        self._registry[capsule_id] = {
            "id": capsule_id,
            "name": metadata.get("name", capsule_id),
            "domain_boundaries": metadata.get("domain_boundaries", []),
            "scent_subscriptions": metadata.get("scent_subscriptions", []),
            "registered": datetime.now().isoformat(),
            **{k: v for k, v in metadata.items() if k not in ["name", "domain_boundaries", "scent_subscriptions"]},
        }

    def unregister(self, capsule_id: str) -> None:
        """Remove a capsule from registry."""
        self._registry.pop(capsule_id, None)

    def list_capsules(self) -> list[dict]:
        """Return all registered capsules with metadata."""
        return list(self._registry.values())

    def get(self, capsule_id: str) -> dict | None:
        """Get a single capsule's metadata."""
        return self._registry.get(capsule_id)

    def route(self, topic: str, payload: dict = None) -> list[str]:
        """
        Find capsules subscribed to a topic.
        Matches exact topic or prefix (e.g., "market.*" matches "market.analysis").
        """
        matches = []
        topic_lower = topic.lower()

        for capsule_id, meta in self._registry.items():
            subscriptions = meta.get("scent_subscriptions", [])
            for sub in subscriptions:
                sub_lower = sub.lower()
                # Exact match
                if sub_lower == topic_lower:
                    matches.append(capsule_id)
                    break
                # Prefix match with wildcard
                if sub_lower.endswith("*") and topic_lower.startswith(sub_lower[:-1]):
                    matches.append(capsule_id)
                    break

        return matches

    def broadcast(self, topic: str, payload: dict) -> dict:
        """Publish message to all subscribed capsules. Returns delivery info."""
        recipients = self.route(topic, payload)
        entry = {
            "topic": topic,
            "payload": payload,
            "recipients": recipients,
            "timestamp": datetime.now().isoformat(),
        }
        self._log.append(entry)

        # Trim log if too long
        if len(self._log) > 1000:
            self._log = self._log[-500:]

        return {"topic": topic, "recipients": recipients, "timestamp": entry["timestamp"]}

    def detect_gaps(self, topic: str) -> bool:
        """Returns True if no capsule handles this topic."""
        return len(self.route(topic)) == 0

    def get_log(self, limit: int = 50) -> list[dict]:
        """Return recent message log entries."""
        return self._log[-limit:]

    def stats(self) -> dict:
        """Return registry statistics."""
        return {
            "capsules": len(self._registry),
            "log_entries": len(self._log),
            "topics": list(set(
                sub for meta in self._registry.values()
                for sub in meta.get("scent_subscriptions", [])
            )),
        }


# -----------------------------------------------------------------------------
# Orchestration - Query-to-Capsule Routing
# -----------------------------------------------------------------------------

def _load_capsule_meta(capsule_path: Path) -> dict | None:
    """
    Load lightweight metadata from a capsule (manifest + definition only).
    Returns None if invalid capsule.
    """
    from aether import get_required_files, validate_folder

    # Check validity
    missing = validate_folder(capsule_path)
    if missing:
        return None

    folder_name = capsule_path.name
    files = get_required_files(folder_name)

    try:
        with open(capsule_path / files["manifest"], "r", encoding="utf-8") as f:
            manifest = json.load(f)
        with open(capsule_path / files["definition"], "r", encoding="utf-8") as f:
            definition = json.load(f)
        with open(capsule_path / files["kg"], "r", encoding="utf-8") as f:
            kg = json.load(f)
        with open(capsule_path / files["kb"], "r", encoding="utf-8") as f:
            kb_text = f.read()
    except (json.JSONDecodeError, IOError):
        return None

    # Extract all rdfs:label values from KG nodes
    kg_labels = []
    for node in kg.get("@graph", []):
        label = node.get("rdfs:label")
        if label:
            kg_labels.append(label)

    return {
        "id": manifest.get("id", folder_name),
        "name": manifest.get("name", folder_name),
        "path": str(capsule_path),
        "agent_type": definition.get("agent_type", "unknown"),
        "agent_name": definition.get("agent_name", ""),
        "primary_function": definition.get("primary_function", ""),
        "trigger_text": definition.get("trigger_text", ""),
        "authoritative": definition.get("domain_boundaries", {}).get("authoritative", []),
        "kg_node_count": len(kg.get("@graph", [])),
        "kg_labels": kg_labels,
        "kb_size": len(kb_text),
    }


def _score_capsule(query_tokens: set, capsule_meta: dict, max_kg_nodes: int) -> dict:
    """
    Score a capsule's relevance to a query.

    Weights:
    - KG label overlap:           0.3
    - trigger_text overlap:       0.25
    - authoritative domain overlap: 0.25
    - capsule name/id overlap:    0.1
    - KG node count (normalized): 0.1
    """
    from aec_concept import tokenize

    # Tokenize capsule fields
    trigger_tokens = tokenize(capsule_meta.get("trigger_text", ""))
    name_tokens = tokenize(capsule_meta.get("name", "") + " " + capsule_meta.get("agent_name", ""))
    primary_tokens = tokenize(capsule_meta.get("primary_function", ""))

    # Tokenize authoritative domains
    domains_text = " ".join(capsule_meta.get("authoritative", []))
    domain_tokens = tokenize(domains_text)

    # Tokenize KG labels (combined text of all rdfs:label values)
    kg_labels_text = " ".join(capsule_meta.get("kg_labels", []))
    kg_label_tokens = tokenize(kg_labels_text)

    # Calculate overlaps
    trigger_overlap = len(query_tokens & trigger_tokens) / max(len(trigger_tokens), 1)
    domain_overlap = len(query_tokens & domain_tokens) / max(len(domain_tokens), 1)
    name_overlap = len(query_tokens & name_tokens) / max(len(name_tokens), 1)
    primary_overlap = len(query_tokens & primary_tokens) / max(len(primary_tokens), 1)
    kg_label_overlap = len(query_tokens & kg_label_tokens) / max(len(query_tokens), 1)

    # Combine trigger and primary function for trigger score
    trigger_score = max(trigger_overlap, primary_overlap)

    # KG node count normalized (tiebreaker)
    kg_count_score = capsule_meta.get("kg_node_count", 0) / max(max_kg_nodes, 1)

    # Weighted sum
    score = (
        kg_label_overlap * 0.3 +
        trigger_score * 0.25 +
        domain_overlap * 0.25 +
        name_overlap * 0.1 +
        kg_count_score * 0.1
    )

    return {
        "capsule_id": capsule_meta["id"],
        "capsule_name": capsule_meta["name"],
        "capsule_path": capsule_meta["path"],
        "score": round(score, 4),
        "kg_label_score": round(kg_label_overlap, 4),
        "trigger_score": round(trigger_score, 4),
        "domain_score": round(domain_overlap, 4),
        "name_score": round(name_overlap, 4),
        "kg_count_score": round(kg_count_score, 4),
        "kg_nodes": capsule_meta.get("kg_node_count", 0),
    }


def orchestrate(query: str, registry_path: str, llm_fn=None, dry_run: bool = False) -> dict:
    """
    Route a query to the best matching capsule, run it, return the result.

    Args:
        query: The query to route
        registry_path: Directory containing capsule folders
        llm_fn: LLM function for the target capsule
        dry_run: If True, return routing decision without executing

    Returns:
        {
            'routed_to': str,          # capsule ID
            'routed_name': str,        # capsule name
            'match_score': float,      # routing confidence 0-1
            'match_method': str,       # how the match was determined
            'candidates': [...],       # all scored candidates
            'result': dict,            # full pipeline result from target capsule
            'gap': dict | None,        # if no match found
        }
    """
    from aether import Capsule
    from aec_concept import tokenize

    registry_path = Path(registry_path)
    query_tokens = tokenize(query)

    # Step 1: Scan registry for valid capsules
    capsule_metas = []
    for item in registry_path.iterdir():
        if not item.is_dir():
            continue

        meta = _load_capsule_meta(item)
        if not meta:
            continue

        # Exclusions
        # Skip router-type agents (prevent loops)
        if meta.get("agent_type") == "router":
            continue

        capsule_metas.append(meta)

    if not capsule_metas:
        return {
            "routed_to": None,
            "routed_name": None,
            "match_score": 0.0,
            "match_method": "no_capsules",
            "candidates": [],
            "result": None,
            "gap": {
                "query": query,
                "topic": " ".join(list(query_tokens)[:5]),
                "closest_capsule": None,
                "closest_score": 0.0,
                "recommendation": "No valid capsules found in registry.",
            },
        }

    # Step 2: Score all capsules
    max_kg_nodes = max(m.get("kg_node_count", 0) for m in capsule_metas)
    candidates = []

    for meta in capsule_metas:
        scored = _score_capsule(query_tokens, meta, max_kg_nodes)
        candidates.append(scored)

    # Sort by score descending
    candidates.sort(key=lambda c: c["score"], reverse=True)

    # Step 3: Select best match or detect gap
    best = candidates[0]

    # Gap threshold: if best score < 0.15, report gap
    if best["score"] < 0.15:
        return {
            "routed_to": None,
            "routed_name": None,
            "match_score": best["score"],
            "match_method": "gap_detected",
            "candidates": candidates[:5],
            "result": None,
            "gap": {
                "query": query,
                "topic": " ".join(list(query_tokens)[:5]),
                "closest_capsule": best["capsule_name"],
                "closest_score": best["score"],
                "recommendation": f"No capsule covers this topic well. Consider stamping a new agent.",
            },
        }

    # Step 4: If dry run, return without executing
    if dry_run:
        return {
            "routed_to": best["capsule_id"],
            "routed_name": best["capsule_name"],
            "match_score": best["score"],
            "match_method": "score_match",
            "candidates": candidates[:5],
            "result": None,
            "gap": None,
            "dry_run": True,
        }

    # Step 5: Load full capsule and run pipeline
    capsule = Capsule(best["capsule_path"], llm_fn=llm_fn)
    result = capsule.run(query)

    return {
        "routed_to": best["capsule_id"],
        "routed_name": best["capsule_name"],
        "match_score": best["score"],
        "match_method": "score_match",
        "candidates": candidates[:5],
        "result": result,
        "gap": None,
    }


if __name__ == "__main__":
    h = Habitat()

    # Register some capsules
    h.register("market-analyst-001", {
        "name": "Market Analyst",
        "scent_subscriptions": ["market.*", "finance.stocks"],
    })
    h.register("weather-001", {
        "name": "Weather Agent",
        "scent_subscriptions": ["weather.*", "alerts.weather"],
    })
    h.register("general-001", {
        "name": "General Assistant",
        "scent_subscriptions": ["general", "help"],
    })

    print(f"Registered: {[c['name'] for c in h.list_capsules()]}")
    print(f"Stats: {h.stats()}")

    # Test routing
    print(f"\nRoute 'market.analysis': {h.route('market.analysis')}")
    print(f"Route 'weather.forecast': {h.route('weather.forecast')}")
    print(f"Route 'unknown.topic': {h.route('unknown.topic')}")

    # Test gap detection
    print(f"\nGap 'market.analysis': {h.detect_gaps('market.analysis')}")
    print(f"Gap 'sports.scores': {h.detect_gaps('sports.scores')}")

    # Test broadcast
    result = h.broadcast("market.analysis", {"query": "AAPL price"})
    print(f"\nBroadcast result: {result}")
    print(f"Log entries: {len(h.get_log())}")
