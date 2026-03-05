"""
AETHER - Adaptive Embodied Thinking Holistic Evolutionary Runtime
Core: Capsule class loads 5 files, runs 4-stage pipeline.
"""

import json
import re
import hashlib
from pathlib import Path

REQUIRED_FILES = {
    "manifest": "manifest.json",
    "definition": "definition.json",
    "persona": "persona.json",
    "kb": "kb.md",
    "kg": "kg.jsonld",
}


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

        files = {}
        for key, filename in REQUIRED_FILES.items():
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
        ctx = {
            "input": input_text,
            "distilled": {},
            "augmented": {},
            "generated": "",
            "review": {},
            "meta": {"capsule_id": self.id, "version": self.version},
        }

        cfg = self.files["definition"].get("pipeline", {})

        if cfg.get("distill", {}).get("enabled", True):
            ctx = self.distill(ctx)
        if cfg.get("augment", {}).get("enabled", True):
            ctx = self.augment(ctx)
        if cfg.get("generate", {}).get("enabled", True):
            ctx = self.generate(ctx)
        if cfg.get("review", {}).get("enabled", True):
            ctx = self.review(ctx)

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
        kg = self.files["kg"]
        nodes = kg.get("@graph", [kg] if "@id" in kg else [])
        kg_context = []
        for node in nodes:
            node_str = json.dumps(node).lower()
            if any(e.lower() in node_str for e in entities):
                kg_context.append(node)
                if len(kg_context) >= 5:
                    break

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
        ctx["generated"] = self.llm_fn(prompt)
        return ctx

    def review(self, ctx: dict) -> dict:
        """Stage 4: Verify response quality."""
        response = ctx["generated"]
        definition = self.files["definition"]

        min_len = definition.get("review", {}).get("min_length", 10)
        max_len = definition.get("review", {}).get("max_length", 10000)

        grounded = len(response) > 10
        length_ok = min_len <= len(response) <= max_len

        ctx["review"] = {
            "grounded": grounded,
            "length_ok": length_ok,
            "passed": grounded and length_ok,
        }
        return ctx

    def __repr__(self) -> str:
        return f"Capsule({self.id!r}, v{self.version})"


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def generate_id(name: str, version: str = "1.0.0") -> str:
    """Generate capsule ID from name and version."""
    h = hashlib.sha256(f"{name}:{version}".encode()).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{h}"


def validate_folder(path: str | Path) -> list[str]:
    """Check if a folder has all required capsule files. Returns missing files."""
    path = Path(path)
    if not path.is_dir():
        return list(REQUIRED_FILES.values())
    return [f for f in REQUIRED_FILES.values() if not (path / f).exists()]


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
