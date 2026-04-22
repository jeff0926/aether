"""
server.py - AETHER REST Backend
Exposes the real Python pipeline to the dashboard browser UI.

Usage:
  python server.py                          # default port 8000
  python server.py --port 8080
  python server.py --provider anthropic     # default LLM
  python server.py --model claude-sonnet-4-6
"""

import argparse
import json
import time
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS

from aether import Capsule
from aec import verify as aec_verify
from habitat import Habitat
from orchestrator import OrchestratorCapsule
from llm import make_llm_fn

app = Flask(__name__)
CORS(app)  # Allow dashboard.html to call from any origin

# Global state - loaded at startup
habitat = Habitat()
capsules = {}
orchestrator = None
DEFAULT_PROVIDER = "stub"
DEFAULT_MODEL = None
REGISTRY_PATH = "registry/agent-registry.jsonld"
EXAMPLES_PATH = "examples"


def load_all_capsules(provider="stub", model=None):
    """Load all capsules into memory."""
    global capsules, orchestrator, habitat

    llm_fn = make_llm_fn(provider=provider, model=model)

    # Load habitat from registry
    count = habitat.load_registry(REGISTRY_PATH)
    print(f"Registered {count} capsules from registry")

    # Load capsule instances
    examples = Path(EXAMPLES_PATH)
    loaded = 0
    for d in sorted(examples.iterdir()):
        if not d.is_dir():
            continue
        try:
            c = Capsule(str(d), llm_fn=llm_fn)
            capsules[d.name] = c
            loaded += 1
        except Exception as e:
            print(f"  Skip {d.name}: {e}")

    print(f"Loaded {loaded} capsules")

    # Create orchestrator with loaded capsules
    orch_path = next(Path(EXAMPLES_PATH).glob("orchestrator*"), None)
    if orch_path:
        orchestrator = OrchestratorCapsule(
            str(orch_path),
            habitat=habitat,
            registry_path=REGISTRY_PATH,
            llm_fn=llm_fn,
            loaded_capsules=capsules
        )
        print(f"Orchestrator ready: {orch_path.name}")
    else:
        print("WARNING: No orchestrator capsule found")


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.route("/health", methods=["GET"])
def health():
    """Return server status, capsule count, registry count."""
    orch_name = None
    if orchestrator:
        orch_name = orchestrator.path.name

    return jsonify({
        "status": "ok",
        "capsules_loaded": len(capsules),
        "registry_count": len(habitat.list_capsules()),
        "orchestrator": orch_name,
        "default_provider": DEFAULT_PROVIDER
    })


@app.route("/registry", methods=["GET"])
def registry():
    """Return the full agent-registry.jsonld content."""
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/settings", methods=["POST"])
def update_settings():
    """
    Test LLM connection with provided settings.
    Body: {"provider": str, "model": str?, "api_key": str?}
    """
    data = request.get_json() or {}
    provider = data.get("provider", "stub")
    model = data.get("model", None)
    api_key = data.get("api_key", None)

    try:
        llm_fn = make_llm_fn(provider=provider, model=model, api_key=api_key)
        # Quick test call
        test_result = llm_fn("Say OK")
        test_text = test_result.get("text", "")

        # Check for error in response
        if "[LLM Error" in test_text:
            return jsonify({
                "status": "error",
                "message": test_text
            }), 400

        return jsonify({
            "status": "ok",
            "provider": provider,
            "model": model or "default",
            "test": "connected",
            "response": test_text[:50]
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


@app.route("/orchestrate", methods=["POST"])
def orchestrate():
    """
    Route a query to the best agent and execute it.
    Body: {"query": str, "provider": str?, "model": str?, "api_key": str?}
    """
    global orchestrator

    data = request.get_json() or {}
    query = data.get("query", "")
    provider = data.get("provider", DEFAULT_PROVIDER)
    model = data.get("model", DEFAULT_MODEL)
    api_key = data.get("api_key", None)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    if not orchestrator:
        return jsonify({"error": "No orchestrator available"}), 500

    start_time = time.time()

    try:
        # Create llm_fn with provided settings (including api_key)
        llm_fn = make_llm_fn(provider=provider, model=model, api_key=api_key)

        # Update capsules with new llm_fn for this request
        for cap in capsules.values():
            cap.llm_fn = llm_fn

        # Create orchestrator with new llm_fn and updated capsules
        orch = OrchestratorCapsule(
            str(orchestrator.path),
            habitat=habitat,
            registry_path=REGISTRY_PATH,
            llm_fn=llm_fn,
            loaded_capsules=capsules
        )

        # Run orchestrator (pure routing + agent execution)
        result = orch.run(query)

        routed_to = result.get("_routed_to", [])
        ghost = result.get("_ghost", False) or result.get("review", {}).get("ghost", False)
        aec = result.get("review", {}).get("aec", {})

        return jsonify({
            "query": query,
            "routed_to": routed_to,
            "routed_capsule_id": result.get("_routed_capsule_id", ""),
            "response": result.get("generated", ""),
            "aec_score": aec.get("score", 0.0),
            "aec_passed": aec.get("passed", False),
            "ghost": ghost,
            "ghost_message": result.get("generated", "") if ghost else None,
            "gap_tokens": result.get("_gap_tokens", []),
            "grounded": aec.get("grounded_statements", 0),
            "ungrounded": aec.get("ungrounded_statements", 0),
            "persona": aec.get("persona_statements", 0),
            "statements": aec.get("statements", []),
            "total_time_ms": round((time.time() - start_time) * 1000, 1)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/verify", methods=["POST"])
def verify():
    """
    Verify text against a capsule's KG.
    Body: {"text": str, "capsule_id": str, "threshold": float?}
    """
    data = request.get_json() or {}
    text = data.get("text", "")
    capsule_id = data.get("capsule_id", "")
    threshold = data.get("threshold", 0.8)

    if not text:
        return jsonify({"error": "Missing text"}), 400

    if not capsule_id or capsule_id not in capsules:
        return jsonify({"error": f"Capsule not found: {capsule_id}"}), 404

    start_time = time.time()

    # Get capsule KG nodes
    capsule = capsules[capsule_id]
    kg_nodes = capsule.files["kg"].get("@graph", [])

    # Run AEC verification
    result = aec_verify(text, kg_nodes, threshold)

    time_ms = (time.time() - start_time) * 1000

    return jsonify({
        "score": result.get("score", 0.0),
        "passed": result.get("passed", False),
        "ghost": result.get("ghost", False),
        "grounded_statements": result.get("grounded", 0),
        "ungrounded_statements": result.get("ungrounded", 0),
        "persona_statements": result.get("persona", 0),
        "statements": result.get("statements", []),
        "gaps": result.get("gaps", []),
        "time_ms": round(time_ms, 2)
    })


@app.route("/run", methods=["POST"])
def run_capsule():
    """
    Run a specific capsule with a query.
    Body: {"capsule_id": str, "query": str, "provider": str?, "model": str?}
    """
    data = request.get_json() or {}
    capsule_id = data.get("capsule_id", "")
    query = data.get("query", "")
    provider = data.get("provider", DEFAULT_PROVIDER)
    model = data.get("model", DEFAULT_MODEL)

    if not query:
        return jsonify({"error": "Missing query"}), 400

    if not capsule_id or capsule_id not in capsules:
        return jsonify({"error": f"Capsule not found: {capsule_id}"}), 404

    start_time = time.time()

    capsule = capsules[capsule_id]

    # If provider specified, create new llm_fn
    if provider != DEFAULT_PROVIDER or model != DEFAULT_MODEL:
        llm_fn = make_llm_fn(provider=provider, model=model)
        # Create temporary capsule with new llm_fn
        temp_capsule = Capsule(str(capsule.path), llm_fn=llm_fn)
    else:
        temp_capsule = capsule

    # Run pipeline
    result = temp_capsule.run(query)

    total_time_ms = int((time.time() - start_time) * 1000)

    return jsonify({
        "capsule_id": capsule_id,
        "capsule_name": temp_capsule.name,
        "agent_type": temp_capsule.files["manifest"].get("agentType", "unknown"),
        "query": query,
        "response": result.get("generated", ""),
        "aec_score": result["review"]["aec"].get("score", 0.0),
        "aec_passed": result["review"]["aec"].get("passed", False),
        "ghost": result["review"]["aec"].get("ghost", False),
        "distilled": result.get("distilled", {}),
        "augmented": {
            "kb_matches": result["augmented"].get("kb_matches", 0),
            "kg_matches": result["augmented"].get("kg_matches", 0)
        },
        "telemetry": {
            "total_ms": total_time_ms
        }
    })


@app.route("/capsules", methods=["GET"])
def list_capsules():
    """Return list of all loaded capsules with metadata."""
    capsule_list = []

    for cid, capsule in capsules.items():
        manifest = capsule.files["manifest"]
        kg = capsule.files["kg"]

        # Count KG nodes
        kg_nodes = len(kg.get("@graph", []))

        # Get topics from registry if available
        reg_entry = habitat.get(cid)
        topics = reg_entry.get("scent_subscriptions", []) if reg_entry else []

        capsule_list.append({
            "id": cid,
            "name": manifest.get("name", cid),
            "agent_type": manifest.get("agentType", "unknown"),
            "version": manifest.get("version", "unknown"),
            "kg_nodes": kg_nodes,
            "topics": topics
        })

    # Sort by name
    capsule_list.sort(key=lambda x: x["name"].lower())

    return jsonify({
        "count": len(capsule_list),
        "capsules": capsule_list
    })


# =============================================================================
# STARTUP
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AETHER REST Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--provider", default="stub",
                        choices=["stub", "anthropic", "openai"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    DEFAULT_PROVIDER = args.provider
    DEFAULT_MODEL = args.model

    print(f"Loading AETHER capsules...")
    load_all_capsules(provider=args.provider, model=args.model)

    print(f"\nAETHER Server running:")
    print(f"  http://{args.host}:{args.port}")
    print(f"  Provider: {args.provider}")
    print(f"  Dashboard: open dashboard.html in browser")
    print(f"  Health: http://{args.host}:{args.port}/health\n")

    app.run(host=args.host, port=args.port, debug=False)
