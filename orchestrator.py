"""
orchestrator.py - OrchestratorCapsule for multi-agent routing and execution

Extends Capsule with registry-aware routing:
- Augment stage reads registry KG to find matching agents
- Generate stage calls Habitat.execute_all() on matches
- Composes multi-agent results into single response
"""

import json
from pathlib import Path
from typing import Callable

from aether import Capsule
from kg import load_kg


class OrchestratorCapsule(Capsule):
    """
    Extends Capsule with registry-aware routing.
    Augment stage reads registry KG to find matching agents.
    Generate stage calls Habitat.execute_all() on matches.
    """

    def __init__(
        self,
        path: str | Path,
        habitat,
        registry_path: str | Path,
        capsule_loader: Callable = None,
        llm_fn: Callable = None
    ):
        """
        Initialize orchestrator.

        Args:
            path: Path to orchestrator capsule folder
            habitat: Habitat instance for routing and execution
            registry_path: Path to agent-registry.jsonld
            capsule_loader: Function to load capsule by ID (capsule_id -> Capsule)
            llm_fn: LLM function for generation
        """
        super().__init__(path, llm_fn)
        self.habitat = habitat
        self.registry_path = Path(registry_path)
        self.registry = load_kg(str(registry_path))
        self.capsule_loader = capsule_loader or self._default_loader
        self._capsule_cache = {}

    def _default_loader(self, capsule_id: str) -> Capsule | None:
        """Default loader - looks in examples/ directory."""
        if capsule_id in self._capsule_cache:
            return self._capsule_cache[capsule_id]

        examples_dir = Path("examples")
        capsule_path = examples_dir / capsule_id

        if capsule_path.exists():
            try:
                capsule = Capsule(str(capsule_path), llm_fn=self.llm_fn)
                self._capsule_cache[capsule_id] = capsule
                return capsule
            except Exception:
                pass

        return None

    def augment(self, ctx: dict) -> dict:
        """Override augment to query registry KG for matching agents."""
        # Standard KB/KG augment first
        ctx = super().augment(ctx)

        # Query registry for matching capsules
        intent = ctx["distilled"].get("intent", "general")
        entities = ctx["distilled"].get("entities", [])
        query = ctx.get("input", "")

        # Find matching agents from registry
        matching_agents = self._find_agents(intent, entities, query)
        ctx["augmented"]["matching_agents"] = matching_agents
        ctx["augmented"]["registry_matches"] = len(matching_agents)

        return ctx

    def _find_agents(self, intent: str, entities: list, query: str) -> list:
        """
        Search registry KG for capsules matching intent and entities.
        Returns list of CapsuleAgent nodes sorted by relevance.
        """
        nodes = self.registry.get("@graph", [])
        matches = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for node in nodes:
            if node.get("@type") != "aether:CapsuleAgent":
                continue

            # Skip self (orchestrator)
            if "orchestrator" in node.get("aether:capsuleId", "").lower():
                continue

            topics = node.get("aether:topics", [])
            domain = node.get("aether:domain", "")
            description = node.get("aether:description", "").lower()
            capabilities = node.get("aether:capability", [])
            label = node.get("rdfs:label", "").lower()
            capsule_id = node.get("aether:capsuleId", "").lower()

            score = 0.0

            # 1. Exact topic match (highest weight)
            topics_lower = [t.lower() for t in topics]
            for word in query_words:
                if word in topics_lower:
                    score += 0.4  # Exact word in topics

            # 2. Topic word overlap
            topic_text = " ".join(topics).lower()
            for word in query_words:
                if len(word) > 3 and word in topic_text:
                    score += 0.15

            # 3. Entity match against topics
            for entity in entities:
                entity_lower = entity.lower()
                for topic in topics_lower:
                    if entity_lower in topic or topic in entity_lower:
                        score += 0.3
                        break

            # 4. Intent/capability match
            capabilities_lower = [c.lower() for c in capabilities]
            if intent.lower() in capabilities_lower:
                score += 0.25
            # Also check query words against capabilities
            for word in query_words:
                if word in capabilities_lower:
                    score += 0.2

            # 5. Capsule name/ID match
            for word in query_words:
                if len(word) > 3 and word in capsule_id:
                    score += 0.3

            # 6. Label match
            for word in query_words:
                if len(word) > 3 and word in label:
                    score += 0.15

            # 7. Description keyword match (lower weight)
            for word in query_words:
                if len(word) > 4 and word in description:
                    score += 0.05

            if score > 0.1:
                matches.append({
                    **node,
                    "_match_score": round(score, 3)
                })

        # Sort by match score descending, then by KG nodes as tiebreaker
        matches.sort(key=lambda x: (
            x.get("_match_score", 0),
            x.get("aether:kgNodes", 0)
        ), reverse=True)

        return matches

    def generate(self, ctx: dict) -> dict:
        """Override generate to execute matched agents via Habitat."""
        matching_agents = ctx["augmented"].get("matching_agents", [])

        if not matching_agents:
            ctx["generated"] = "[GHOST] No suitable agent found for this query."
            ctx["review"] = {
                "ghost": True,
                "aec": {"score": 0.0, "passed": False, "ghost": True}
            }
            ctx["_routed_to"] = []
            ctx["_agent_results"] = []
            return ctx

        # Get max_agents from definition
        orch_config = self.files["definition"].get("orchestrator", {})
        max_agents = orch_config.get("max_agents", 3)

        # Get capsule IDs to execute
        capsule_ids = [
            a["aether:capsuleId"] for a in matching_agents[:max_agents]
        ]

        # Load capsules
        capsules = {}
        for cid in capsule_ids:
            capsule = self.capsule_loader(cid)
            if capsule:
                capsules[cid] = capsule

        if not capsules:
            ctx["generated"] = "[GHOST] No agents could be loaded for execution."
            ctx["review"] = {
                "ghost": True,
                "aec": {"score": 0.0, "passed": False, "ghost": True}
            }
            ctx["_routed_to"] = []
            ctx["_agent_results"] = []
            return ctx

        # Execute via Habitat (pass explicit capsule_ids to skip topic routing)
        results = self.habitat.execute_all(
            topic=ctx["distilled"].get("intent", "general"),
            query=ctx["input"],
            capsules=capsules,
            max_agents=max_agents,
            capsule_ids=capsule_ids
        )

        # Compose response
        ctx["generated"] = self._compose_response(results)
        ctx["_routed_to"] = [r.get("capsule_name", r.get("capsule_id")) for r in results]
        ctx["_agent_results"] = results

        # Aggregate AEC scores
        scores = [r["aec_score"] for r in results if "aec_score" in r]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        all_passed = all(r.get("aec_passed", False) for r in results if "aec_passed" in r)
        any_ghost = any(r.get("ghost", False) for r in results)

        ctx["review"] = {
            "aec": {
                "score": round(avg_score, 3),
                "passed": all_passed and not any_ghost,
                "ghost": any_ghost and not all_passed,
                "agents_executed": len(results),
            },
            "ghost": any_ghost and not all_passed,
            "queued": False,
            "self_corrected": False,
        }

        return ctx

    def _compose_response(self, results: list) -> str:
        """Compose multi-agent results into single response."""
        if not results:
            return "[GHOST] No agents executed."

        parts = []
        for r in results:
            if r.get("error"):
                parts.append(
                    f"[{r.get('capsule_name', r['capsule_id'])}] ERROR: {r['error']}"
                )
            elif r.get("ghost"):
                parts.append(
                    f"[{r['capsule_name']}] GHOST — could not verify response (AEC: {r['aec_score']:.2f})"
                )
            else:
                parts.append(
                    f"[{r['capsule_name']} — AEC: {r['aec_score']:.2f}]\n"
                    f"{r['response']}"
                )

        return "\n\n---\n\n".join(parts)

    def review(self, ctx: dict) -> dict:
        """Override review - already handled in generate for orchestrator."""
        # Review is done in generate() for orchestrator
        # Just ensure review dict exists
        if "review" not in ctx:
            ctx["review"] = {
                "aec": {"score": 0.0, "passed": False, "ghost": True},
                "ghost": True,
                "queued": False,
                "self_corrected": False,
            }
        return ctx


def orchestrate(
    query: str,
    habitat,
    registry_path: str = "registry/agent-registry.jsonld",
    orchestrator_path: str = None,
    llm_fn: Callable = None,
    max_agents: int = 3
) -> dict:
    """
    Convenience function to run orchestration.

    Args:
        query: The query to route and execute
        habitat: Habitat instance with registered capsules
        registry_path: Path to agent registry KG
        orchestrator_path: Path to orchestrator capsule (auto-detects if None)
        llm_fn: LLM function for capsules
        max_agents: Max agents to execute

    Returns:
        Orchestration result dict
    """
    # Auto-detect orchestrator capsule
    if orchestrator_path is None:
        orch_match = list(Path("examples").glob("orchestrator*"))
        if orch_match:
            orchestrator_path = str(orch_match[0])
        else:
            raise ValueError("No orchestrator capsule found in examples/")

    # Create orchestrator
    orch = OrchestratorCapsule(
        orchestrator_path,
        habitat=habitat,
        registry_path=registry_path,
        llm_fn=llm_fn
    )

    # Run pipeline
    result = orch.run(query)

    return {
        "query": query,
        "routed_to": result.get("_routed_to", []),
        "agent_results": result.get("_agent_results", []),
        "response": result["generated"],
        "aec": result["review"]["aec"],
        "ghost": result["review"].get("ghost", False),
    }


if __name__ == "__main__":
    # Test orchestrator
    from habitat import Habitat
    from llm import make_llm_fn

    print("Loading habitat from registry...")
    h = Habitat()

    # Manual registration for test
    registry = load_kg("registry/agent-registry.jsonld")
    for node in registry.get("@graph", []):
        if node.get("@type") == "aether:CapsuleAgent":
            h.register(node["aether:capsuleId"], {
                "name": node.get("rdfs:label"),
                "scent_subscriptions": node.get("aether:topics", []),
            })

    print(f"Registered {len(h.list_capsules())} capsules")

    # Find orchestrator
    orch_path = list(Path("examples").glob("orchestrator*"))[0]
    print(f"Orchestrator: {orch_path.name}")

    # Create and test
    orch = OrchestratorCapsule(
        str(orch_path),
        habitat=h,
        registry_path="registry/agent-registry.jsonld",
        llm_fn=make_llm_fn("stub")
    )

    # Test query
    result = orch.run("Create a professional document")
    print(f"\nQuery: Create a professional document")
    print(f"Routed to: {result.get('_routed_to')}")
    print(f"Response preview: {result['generated'][:200]}...")
