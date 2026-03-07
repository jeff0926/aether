"""
AETHER - Adaptive Embodied Thinking Holistic Evolutionary Runtime
Core: Capsule class loads 5 files, runs 4-stage pipeline.
"""

import json
import re
import hashlib
import time
from pathlib import Path
from datetime import datetime

from aec import verify as aec_verify
from kg import query_nodes as kg_query
from education import queue_failure

# File suffixes for capsule files: {folder-name}{suffix}
REQUIRED_SUFFIXES = {
    "manifest": "-manifest.json",
    "definition": "-definition.json",
    "persona": "-persona.json",
    "kb": "-kb.md",
    "kg": "-kg.jsonld",
}


def get_required_files(folder_name: str) -> dict:
    """Derive filenames from folder name. Pattern: {folder-name}-{type}.{ext}"""
    return {key: f"{folder_name}{suffix}" for key, suffix in REQUIRED_SUFFIXES.items()}


class Capsule:
    """
    A capsule is a folder with 5 files defining an agent's identity and knowledge.
    Pipeline: distill → augment → generate → review
    """

    def __init__(self, path: str | Path, llm_fn: callable = None):
        self.path = Path(path)
        self.llm_fn = llm_fn or (lambda p, **kw: f"[No LLM. Prompt: {len(p)} chars]")
        self.files = self._load_files()

    def _load_files(self) -> dict:
        if not self.path.is_dir():
            raise ValueError(f"Capsule path must be a directory: {self.path}")

        folder_name = self.path.name
        required_files = get_required_files(folder_name)

        files = {}
        for key, filename in required_files.items():
            filepath = self.path / filename
            if not filepath.exists():
                raise FileNotFoundError(f"Missing: {filename}")

            with open(filepath, "r", encoding="utf-8") as f:
                files[key] = f.read() if key == "kb" else json.load(f)

        # Validate manifest
        if "id" not in files["manifest"]:
            raise ValueError("manifest.json must have 'id'")
        if "version" not in files["manifest"]:
            raise ValueError("manifest.json must have 'version'")

        # Default pipeline config if missing
        if "pipeline" not in files["definition"]:
            files["definition"]["pipeline"] = {
                "distill": {"enabled": True},
                "augment": {"enabled": True},
                "generate": {"enabled": True},
                "review": {"enabled": True},
            }

        return files

    @property
    def id(self) -> str:
        return self.files["manifest"]["id"]

    @property
    def name(self) -> str:
        return self.files["manifest"].get("name", self.id)

    @property
    def version(self) -> str:
        return self.files["manifest"]["version"]

    # -------------------------------------------------------------------------
    # Pipeline
    # -------------------------------------------------------------------------

    def run(self, input_text: str) -> dict:
        """Run full 4-stage pipeline. Returns context dict with all results."""
        start_time = time.time()
        ctx = {
            "input": input_text,
            "distilled": {},
            "augmented": {},
            "generated": "",
            "review": {},
            "meta": {"capsule_id": self.id, "version": self.version},
            "telemetry": {"start": start_time, "stages": {}},
        }

        cfg = self.files["definition"].get("pipeline", {})

        if cfg.get("distill", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.distill(ctx)
            ctx["telemetry"]["stages"]["distill"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
                "entities_extracted": len(ctx["distilled"].get("entities", [])),
            }

        if cfg.get("augment", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.augment(ctx)
            ctx["telemetry"]["stages"]["augment"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
                "kb_matches": len(ctx["augmented"].get("kb", [])),
                "kg_matches": len(ctx["augmented"].get("kg", [])),
            }

        if cfg.get("generate", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.generate(ctx)
            ctx["telemetry"]["stages"]["generate"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
                "prompt_chars": ctx.get("_prompt_len", 0),
                "tokens_in": ctx.get("_tokens_in", 0),
                "tokens_out": ctx.get("_tokens_out", 0),
            }

        if cfg.get("review", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.review(ctx)
            ctx["telemetry"]["stages"]["review"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
            }

        ctx["telemetry"]["total_ms"] = round((time.time() - start_time) * 1000, 2)
        return ctx

    def distill(self, ctx: dict) -> dict:
        """Stage 1: Extract intent, entities, constraints from input."""
        text = ctx["input"]
        text_lower = text.lower()

        # Intent detection
        if any(w in text_lower for w in ["what is", "who is", "explain"]):
            intent = "query"
        elif any(w in text_lower for w in ["how to", "how do", "steps"]):
            intent = "instruction"
        elif any(w in text_lower for w in ["compare", "versus", "difference"]):
            intent = "comparison"
        elif any(w in text_lower for w in ["create", "generate", "write"]):
            intent = "creation"
        else:
            intent = "general"

        # Entity extraction: capitalized words not at sentence start
        words = text.split()
        entities = list(set(
            w for i, w in enumerate(words)
            if i > 0 and w and w[0].isupper() and w.isalpha()
        ))

        # Format detection
        fmt = None
        if "list" in text_lower or "bullet" in text_lower:
            fmt = "list"
        elif "table" in text_lower:
            fmt = "table"
        elif "json" in text_lower:
            fmt = "json"

        ctx["distilled"] = {
            "intent": intent,
            "entities": entities,
            "brevity": any(w in text_lower for w in ["brief", "short", "concise"]),
            "format": fmt,
        }
        return ctx

    def augment(self, ctx: dict) -> dict:
        """Stage 2: Enrich with KB and KG context."""
        entities = ctx["distilled"].get("entities", [])

        # Search KB paragraphs
        paragraphs = [p.strip() for p in self.files["kb"].split("\n\n") if p.strip()]
        kb_matches = []
        for para in paragraphs:
            para_lower = para.lower()
            score = sum(1 for e in entities if e.lower() in para_lower)
            if score > 0:
                kb_matches.append((score, para))
        kb_matches.sort(reverse=True, key=lambda x: x[0])
        kb_context = [p for _, p in kb_matches[:3]]

        # Search KG nodes
        kg_context = kg_query(self.files["kg"], entities)
        if len(kg_context) > 5:
            kg_context = kg_context[:5]

        ctx["augmented"] = {
            "kb": kb_context,
            "kg": kg_context,
            "persona": {
                "tone": self.files["persona"].get("tone", "neutral"),
                "style": self.files["persona"].get("style", "informative"),
            },
        }
        return ctx

    def generate(self, ctx: dict) -> dict:
        """Stage 3: Build prompt and call LLM."""
        aug = ctx["augmented"]
        parts = [f"You are: {self.name}"]

        if aug.get("persona"):
            parts.append(f"Tone: {aug['persona'].get('tone', 'neutral')}")

        parts.append("\nIMPORTANT: Use exact figures, dates, and names from the provided knowledge. Do not round, approximate, or paraphrase numerical values. Cite precisely.")

        if aug.get("kb"):
            parts.append("\nKnowledge:")
            for kb in aug["kb"]:
                parts.append(f"- {kb[:200]}...")

        if aug.get("kg"):
            parts.append("\nConcepts:")
            for node in aug["kg"]:
                label = node.get("rdfs:label", node.get("@id", "?"))
                parts.append(f"- {label}")

        parts.append(f"\nQuery: {ctx['input']}")
        parts.append("\nResponse:")

        prompt = "\n".join(parts)
        ctx["_prompt_len"] = len(prompt)

        result = self.llm_fn(prompt)
        # Handle dict response (with tokens) or string response
        if isinstance(result, dict):
            ctx["generated"] = result.get("text", "")
            ctx["_tokens_in"] = result.get("tokens_in", 0)
            ctx["_tokens_out"] = result.get("tokens_out", 0)
        else:
            ctx["generated"] = result
            ctx["_tokens_in"] = 0
            ctx["_tokens_out"] = 0

        return ctx

    def review(self, ctx: dict) -> dict:
        """Stage 4: Verify response quality via AEC."""
        response = ctx["generated"]
        # Handle both dict and string from LLM
        if isinstance(response, dict):
            response_text = response.get("text", str(response))
        else:
            response_text = str(response)

        definition = self.files["definition"]
        kg_nodes = ctx["augmented"].get("kg", [])
        threshold = definition.get("review", {}).get("threshold", 0.8)

        # Run AEC verification against augmented KG subgraph
        aec_result = aec_verify(response_text, kg_nodes, threshold)

        # Queue failures for education
        queued = False
        if not aec_result["passed"]:
            queue_failure(self.path, ctx["input"], response_text, aec_result)
            queued = True

        ctx["review"] = {
            "aec": aec_result,
            "passed": aec_result["passed"],
            "queued": queued,
        }
        return ctx

    def __repr__(self) -> str:
        return f"Capsule({self.id!r}, v{self.version})"


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def generate_id(name: str, version: str = "1.0.0") -> str:
    """Generate capsule ID: {slug}-v{version}-{uid8}."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    raw = f"{name}:{version}:{datetime.now().isoformat()}"
    uid = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{slug}-v{version}-{uid}"


def validate_folder(path: str | Path) -> list[str]:
    """Check if a folder has all required capsule files. Returns missing files."""
    path = Path(path)
    if not path.is_dir():
        return [f"{path.name}{s}" for s in REQUIRED_SUFFIXES.values()]
    required_files = get_required_files(path.name)
    return [f for f in required_files.values() if not (path / f).exists()]


# -----------------------------------------------------------------------------
# CLI Test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
        missing = validate_folder(path)
        if missing:
            print(f"Missing files: {missing}")
            sys.exit(1)
        cap = Capsule(path)
        print(cap)
        print(f"KB: {len(cap.files['kb'])} chars")
        print(f"KG: {len(cap.files['kg'].get('@graph', []))} nodes")
    else:
        print("Usage: python aether.py <capsule_folder>")
