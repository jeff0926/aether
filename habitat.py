"""
Habitat - Capsule registry with message routing.
Where capsules live, discover each other, and exchange signals.
"""

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
