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
        Score all registry agents against intent + entities.
        Return single best match. Multi-agent only if tied scores
        AND query spans multiple domains.
        """
        import re
        nodes = self.registry.get("@graph", [])
        scored = []

        # Normalize query terms from entities (skip short terms like "I")
        query_terms = set(e.lower() for e in entities if len(e) >= 3)
        # Also add intent as a term
        query_terms.add(intent.lower())

        # Also extract key words from query (fallback when entities empty)
        # Skip common stopwords
        stopwords = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
                     'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
                     'i', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its', 'how',
                     'what', 'when', 'where', 'why', 'who', 'which', 'that', 'this',
                     'create', 'make', 'build', 'get', 'tell', 'give', 'use', 'want'}
        query_words = re.findall(r'[a-z]+', query.lower())
        for word in query_words:
            if len(word) > 2 and word not in stopwords:
                query_terms.add(word)

        for node in nodes:
            if node.get("@type") != "aether:CapsuleAgent":
                continue

            capsule_id = node.get("aether:capsuleId", "")
            topics = [t.lower() for t in node.get("aether:topics", [])]
            description = node.get("aether:description", "").lower()
            domain = node.get("aether:domain", "").lower()
            agent_type = node.get("aether:agentType", "domain")
            capabilities = [c.lower() for c in node.get("aether:capability", [])]

            # Skip orchestrator routing to itself
            if agent_type == "orchestrator":
                continue

            # SCORE: count how many query terms match this agent
            # Track content relevance separately from capability match
            content_score = 0  # topic/domain/description matches
            capability_score = 0

            # Topic exact match — highest weight (3 points each)
            # Only do substring matching for terms >= 3 chars
            for term in query_terms:
                if len(term) < 3:
                    continue
                for topic in topics:
                    if term == topic or term in topic or topic in term:
                        content_score += 3

            # Domain match — high weight (2 points)
            for term in query_terms:
                if len(term) >= 3 and term in domain:
                    content_score += 2

            # Description match — medium weight (1 point)
            for term in query_terms:
                if len(term) >= 3 and term in description:
                    content_score += 1

            # Intent → capability match (2 points)
            INTENT_CAPABILITY_MAP = {
                "creation": ["create", "generate", "build", "format"],
                "query":    ["explain", "answer", "research", "advise"],
                "instruction": ["create", "format", "build", "advise"],
                "comparison": ["analyze", "evaluate", "compare"],
                "general":  ["advise", "answer", "explain"]
            }
            expected_capabilities = INTENT_CAPABILITY_MAP.get(intent.lower(), [])
            for cap in capabilities:
                if cap in expected_capabilities:
                    capability_score += 2

            # Require at least SOME content relevance (topic/domain/description)
            # Capability match alone is not enough - prevents generic matching
            score = content_score + capability_score
            if content_score > 0 and score > 0:
                scored.append({
                    "node": node,
                    "score": score,
                    "capsule_id": capsule_id,
                    "agent_type": agent_type
                })

        if not scored:
            return []

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)

        # Return SINGLE best match unless:
        # - Top 2 scores are within 1 point of each other AND
        # - They are from DIFFERENT domains (genuine multi-domain query)
        best_score = scored[0]["score"]
        best_domain = scored[0]["node"].get("aether:domain", "")

        results = [scored[0]["node"]]

        if len(scored) > 1:
            second = scored[1]
            second_domain = second["node"].get("aether:domain", "")
            score_gap = best_score - second["score"]

            # Only add second agent if:
            # 1. Score gap is <= 1 (genuinely tied)
            # 2. Different domain (not just another docx variant)
            if score_gap <= 1 and second_domain != best_domain:
                results.append(second["node"])

        return results

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
