"""
orchestrator.py - OrchestratorCapsule for query routing

Pure router — no AEC on routing decision:
1. Distill query → intent + entities
2. Score registry → single best agent
3. Execute that agent (full DAGR + AEC)
4. Return agent result directly
"""

import time
from pathlib import Path
from typing import Callable

from aether import Capsule
from kg import load_kg


class OrchestratorCapsule(Capsule):
    """
    Pure router. Extends Capsule only to use distill().
    Does NOT run augment/generate/review on routing.
    """

    def __init__(
        self,
        path: str | Path,
        habitat,
        registry_path: str | Path,
        llm_fn: Callable = None,
        loaded_capsules: dict = None
    ):
        """
        Initialize orchestrator.

        Args:
            path: Path to orchestrator capsule folder
            habitat: Habitat instance for routing
            registry_path: Path to agent-registry.jsonld
            llm_fn: LLM function for capsules
            loaded_capsules: Dict of capsule_id -> Capsule instances
        """
        super().__init__(path, llm_fn)
        self.habitat = habitat
        self.registry_path = Path(registry_path)
        self.registry = load_kg(str(registry_path))
        self._loaded_capsules = loaded_capsules or {}

    def run(self, query: str) -> dict:
        """
        Pure router. No AEC on routing decision.

        1. Distill query → intent + entities
        2. Score registry → single best agent
        3. Execute that agent → real response + real AEC
        4. Return agent result directly
        """
        start = time.time()

        # Step 1: Distill — extract intent and entities
        ctx = {
            "input": query,
            "distilled": {},
            "augmented": {},
            "generated": "",
            "review": {},
            "meta": {"capsule_id": self.id},
            "telemetry": {"stages": {}}
        }
        ctx = self.distill(ctx)

        intent = ctx["distilled"].get("intent", "general")
        entities = ctx["distilled"].get("entities", [])

        # Step 2: Score registry — find single best agent
        matching_agents = self._find_agents(intent, entities, query)

        if not matching_agents:
            return {
                "input": query,
                "generated": "[GHOST] No suitable agent found for this query.",
                "review": {
                    "ghost": True,
                    "aec": {"score": 0.0, "passed": False, "ghost": True}
                },
                "_routed_to": [],
                "_routed_capsule_id": None,
                "_ghost": True,
                "_gap_tokens": [e.lower() for e in entities if len(e) >= 3],
                "telemetry": {
                    "total_ms": round((time.time() - start) * 1000, 1)
                }
            }

        # Step 3: Execute the single best agent
        best_agent = matching_agents[0]
        capsule_id = best_agent.get("aether:capsuleId")
        routing_score = best_agent.get("_score", 0)
        capsule = self._get_capsule(capsule_id)

        if not capsule:
            return {
                "input": query,
                "generated": f"[GHOST] Agent {capsule_id} not loaded.",
                "review": {
                    "ghost": True,
                    "aec": {"score": 0.0, "passed": False, "ghost": True}
                },
                "_routed_to": [],
                "_routed_capsule_id": capsule_id,
                "_ghost": True,
                "telemetry": {
                    "total_ms": round((time.time() - start) * 1000, 1)
                }
            }

        # Run the selected agent — FULL DAGR including AEC (skip distill, already done)
        agent_result = capsule.run_from_ctx(ctx)

        # Step 4: Return agent result directly with routing metadata
        routing_ms = round((time.time() - start) * 1000, 1)
        agent_result["_routed_to"] = [best_agent.get("rdfs:label", capsule_id)]
        agent_result["_routed_capsule_id"] = capsule_id
        agent_result["_routing_score"] = routing_score
        if "telemetry" not in agent_result:
            agent_result["telemetry"] = {}
        agent_result["telemetry"]["routing_ms"] = routing_ms

        return agent_result

    def _get_capsule(self, capsule_id: str) -> Capsule | None:
        """Find loaded capsule by ID or folder name."""
        # Try exact match first
        if capsule_id in self._loaded_capsules:
            return self._loaded_capsules[capsule_id]
        # Try folder name match (capsule_id might be full folder name)
        for key, capsule in self._loaded_capsules.items():
            if capsule_id in key or key in capsule_id:
                return capsule
        return None

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
                # Store score in node for later reference
                node_copy = dict(node)
                node_copy["_score"] = score
                scored.append({
                    "node": node_copy,
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
        best = scored[0]
        best_score = best["score"]
        best_domain = best["node"].get("aether:domain", "")

        results = [best["node"]]

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


def orchestrate(
    query: str,
    habitat,
    registry_path: str = "registry/agent-registry.jsonld",
    orchestrator_path: str = None,
    llm_fn: Callable = None,
    loaded_capsules: dict = None
) -> dict:
    """
    Convenience function to run orchestration.

    Args:
        query: The query to route and execute
        habitat: Habitat instance with registered capsules
        registry_path: Path to agent registry KG
        orchestrator_path: Path to orchestrator capsule (auto-detects if None)
        llm_fn: LLM function for capsules
        loaded_capsules: Dict of capsule_id -> Capsule instances

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
        llm_fn=llm_fn,
        loaded_capsules=loaded_capsules
    )

    # Run pipeline
    result = orch.run(query)

    return {
        "query": query,
        "routed_to": result.get("_routed_to", []),
        "routed_capsule_id": result.get("_routed_capsule_id"),
        "response": result.get("generated", ""),
        "aec": result.get("review", {}).get("aec", {}),
        "ghost": result.get("review", {}).get("ghost", False),
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

    # Load capsules
    capsules = {}
    for d in Path("examples").iterdir():
        if d.is_dir():
            try:
                c = Capsule(str(d), llm_fn=make_llm_fn("stub"))
                capsules[d.name] = c
            except:
                pass

    print(f"Loaded {len(capsules)} capsules")

    # Find orchestrator
    orch_path = list(Path("examples").glob("orchestrator*"))[0]
    print(f"Orchestrator: {orch_path.name}")

    # Create and test
    orch = OrchestratorCapsule(
        str(orch_path),
        habitat=h,
        registry_path="registry/agent-registry.jsonld",
        llm_fn=make_llm_fn("stub"),
        loaded_capsules=capsules
    )

    # Test query
    result = orch.run("Create a professional document")
    print(f"\nQuery: Create a professional document")
    print(f"Routed to: {result.get('_routed_to')}")
    print(f"AEC score: {result.get('review', {}).get('aec', {}).get('score', 0)}")
    print(f"Response preview: {result.get('generated', '')[:200]}...")
