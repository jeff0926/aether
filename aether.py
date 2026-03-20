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
    Optional 6th file: PSI projection layer for UI state emission.
    """

    def __init__(self, path: str | Path, llm_fn: callable = None):
        self.path = Path(path)
        self.llm_fn = llm_fn or (lambda p, **kw: f"[No LLM. Prompt: {len(p)} chars]")
        self.files = self._load_files()
        self.resolved_provider = None
        self.resolved_model = None
        self._compiled_kg = self._compile_kg_if_typed()

        # PSI Layer (optional)
        self.psi = self._load_psi()
        self.psi_enabled = self.files["definition"].get("psi_enabled", False)

        # Initialize emitter if PSI enabled
        if self.psi_enabled:
            from psi import AetherEmitter
            agent_name = self.files["manifest"].get("name", self.path.name)
            scope = f"#aether-{self.path.name}"
            if self.psi:
                scope = self.psi.get("psi:default_scope", scope).replace("{agent_name}", self.path.name)
            self._emitter = AetherEmitter(agent_name, scope)
        else:
            self._emitter = None

        # Resolve LLM from definition.json if present
        self._resolve_llm()

    def _resolve_llm(self):
        """Resolve provider/model from definition.json llm block if present."""
        from llm import resolve_model, make_llm_fn

        llm_block = self.files["definition"].get("llm")
        if not llm_block:
            return  # no llm block — leave everything unchanged

        provider, model = resolve_model(
            capability=llm_block.get("capability", "default"),
            preferred_provider=llm_block.get("preferred_provider"),
            preferred_model=llm_block.get("preferred_model")
        )
        self.resolved_provider = provider
        self.resolved_model = model

        # Only replace llm_fn if caller did not supply one
        # (i.e. it's still the default no-op lambda)
        if self.llm_fn.__name__ == "<lambda>":
            self.llm_fn = make_llm_fn(provider=provider, model=model)

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

    def _compile_kg_if_typed(self) -> dict | None:
        """Compile KG for concept AEC if it has typed nodes (Rule, Technique, etc.)."""
        from aec_concept import compile_kg, has_typed_nodes
        kg_nodes = self.files["kg"].get("@graph", [])
        if has_typed_nodes(kg_nodes):
            return compile_kg(kg_nodes)
        return None

    def _load_psi(self) -> dict | None:
        """Load optional PSI file if present. Returns None if no PSI file."""
        psi_files = list(self.path.glob("*-psi.jsonld"))
        if not psi_files:
            return None
        try:
            with open(psi_files[0], "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

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

    def run(self, input_text: str, emit_psi: bool = False) -> dict:
        """
        Run full 4-stage pipeline. Returns context dict with all results.

        Args:
            input_text: Query or input to process
            emit_psi: If True, include psi_events in result (requires psi_enabled)

        Returns:
            Context dict with pipeline results. If emit_psi=True and psi_enabled,
            includes 'psi_events' list of SSE-formatted CVP event strings.
        """
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

        # PSI event collection
        psi_events = []
        should_emit_psi = emit_psi and self.psi_enabled and self._emitter

        cfg = self.files["definition"].get("pipeline", {})

        # Stage 1: Distill
        if cfg.get("distill", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.distill(ctx)
            ctx["telemetry"]["stages"]["distill"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
                "entities_extracted": len(ctx["distilled"].get("entities", [])),
            }
            # PSI: Reflex phase
            if should_emit_psi:
                psi_events.append(self._emitter.pulse(
                    "reflex",
                    {"--aether-view-complexity": "0.2", "--aether-confidence": "0"}
                ))

        # Stage 2: Augment
        if cfg.get("augment", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.augment(ctx)
            ctx["telemetry"]["stages"]["augment"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
                "kb_matches": len(ctx["augmented"].get("kb", [])),
                "kg_matches": len(ctx["augmented"].get("kg", [])),
            }
            # PSI: Deliberation phase (start)
            if should_emit_psi:
                psi_events.append(self._emitter.pulse(
                    "deliberation",
                    {"--aether-view-complexity": "0.4"}
                ))

        # Stage 3: Generate
        if cfg.get("generate", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.generate(ctx)
            ctx["telemetry"]["stages"]["generate"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
                "prompt_chars": ctx.get("_prompt_len", 0),
                "tokens_in": ctx.get("_tokens_in", 0),
                "tokens_out": ctx.get("_tokens_out", 0),
            }
            # PSI: Deliberation phase (mid)
            if should_emit_psi:
                psi_events.append(self._emitter.pulse(
                    "deliberation",
                    {"--aether-view-complexity": "0.7"}
                ))

        # Stage 4: Review
        if cfg.get("review", {}).get("enabled", True):
            t0 = time.time()
            ctx = self.review(ctx)
            ctx["telemetry"]["stages"]["review"] = {
                "time_ms": round((time.time() - t0) * 1000, 2),
            }
            # PSI: Complete or Ghost phase
            if should_emit_psi:
                from psi import _detect_sentiment
                review = ctx.get("review", {})
                aec_data = review.get("aec", {})
                aec_score = aec_data.get("score", 0)
                aec_passed = review.get("passed", False)
                is_ghost = review.get("ghost", False)
                response = ctx.get("generated", "")

                if aec_passed and not is_ghost:
                    psi_events.append(self._emitter.pulse(
                        "complete",
                        {
                            "--aether-view-complexity": "1.0",
                            "--aether-confidence": str(round(aec_score, 2)),
                            "--aether-sentiment": _detect_sentiment(response),
                        },
                        content=response,
                        aec_score=aec_score,
                    ))
                else:
                    psi_events.append(self._emitter.pulse(
                        "ghost",
                        {
                            "--aether-view-complexity": "0.1",
                            "--aether-confidence": "0",
                            "--aether-sentiment": "negative",
                        },
                        content=None,
                        aec_score=aec_score,
                        reason=f"AEC score {aec_score:.2f} below threshold" if aec_score else "Verification failed",
                    ))

        ctx["telemetry"]["total_ms"] = round((time.time() - start_time) * 1000, 2)

        # Include PSI events if requested
        if emit_psi:
            ctx["psi_events"] = psi_events

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

        # Keyword extraction: significant lowercase words from query
        stop_words = {"what", "how", "when", "where", "who", "why",
                      "is", "are", "was", "were", "do", "does", "did",
                      "the", "a", "an", "to", "of", "in", "for", "on",
                      "and", "or", "but", "not", "my", "i", "me", "it",
                      "this", "that", "with", "from", "by", "at", "can",
                      "should", "would", "could", "need", "before", "after",
                      "much", "many", "some", "all", "any", "about"}
        keywords = [w.lower() for w in words
                    if w.lower() not in stop_words and len(w) > 2]

        ctx["distilled"] = {
            "intent": intent,
            "entities": entities,
            "keywords": keywords,
            "brevity": any(w in text_lower for w in ["brief", "short", "concise"]),
            "format": fmt,
        }
        return ctx

    def augment(self, ctx: dict) -> dict:
        """Stage 2: Enrich with KB and KG context."""
        entities = ctx["distilled"].get("entities", [])
        search_terms = entities + ctx["distilled"].get("keywords", [])

        # Check for markdown headers in KB
        kb_text = self.files["kb"]
        has_headers = any(line.strip().startswith("##") for line in kb_text.split("\n"))

        if has_headers:
            # Two-pass progressive augment
            kb_pass = "two-pass"

            # Pass 1: Structure scan - split on headers
            sections = []
            current_header = ""
            current_body = []

            for line in kb_text.split("\n"):
                if line.strip().startswith("##"):
                    # Save previous section
                    if current_header or current_body:
                        sections.append((current_header, "\n".join(current_body).strip()))
                    current_header = line.strip()
                    current_body = []
                else:
                    current_body.append(line)

            # Don't forget the last section
            if current_header or current_body:
                sections.append((current_header, "\n".join(current_body).strip()))

            # Score sections
            kb_matches = []
            for header, body in sections:
                if not header and not body:
                    continue

                header_lower = header.lower()
                body_lower = body.lower()

                # Pass 1 scoring
                # +2 for each entity matched in header
                header_score = sum(2 for t in search_terms if t.lower() in header_lower)

                # +1 for each entity matched in first sentence of body
                first_sentence = body.split(".")[0] if body else ""
                first_sentence_lower = first_sentence.lower()
                first_sentence_score = sum(1 for t in search_terms if t.lower() in first_sentence_lower)

                pass1_score = header_score + first_sentence_score

                if pass1_score > 0:
                    # Pass 2: Content pull - score full body
                    body_score = sum(1 for t in search_terms if t.lower() in body_lower)
                    final_score = pass1_score + body_score

                    # Reconstruct full section text
                    full_section = f"{header}\n{body}".strip() if header else body
                    kb_matches.append((final_score, full_section))

            kb_matches.sort(reverse=True, key=lambda x: x[0])
            kb_context = [p for _, p in kb_matches[:3]]

        else:
            # Fallback: original paragraph-split logic
            kb_pass = "fallback"

            paragraphs = [p.strip() for p in kb_text.split("\n\n") if p.strip()]
            kb_matches = []
            for para in paragraphs:
                para_lower = para.lower()
                score = sum(1 for t in search_terms if t.lower() in para_lower)
                if score > 0:
                    kb_matches.append((score, para))
            kb_matches.sort(reverse=True, key=lambda x: x[0])
            kb_context = [p for _, p in kb_matches[:3]]

        # Search KG nodes
        kg_context = kg_query(self.files["kg"], search_terms)
        if len(kg_context) > 5:
            kg_context = kg_context[:5]

        ctx["augmented"] = {
            "kb": kb_context,
            "kg": kg_context,
            "kb_pass": kb_pass,
            "persona": {
                "tone": self.files["persona"].get("tone", "neutral"),
                "style": self.files["persona"].get("style", "informative"),
            },
        }
        return ctx

    def _build_prompt(self, ctx: dict, constraints: list[str] = None) -> str:
        """Build LLM prompt from context. Optionally add knowledge constraints."""
        aug = ctx["augmented"]
        parts = [f"You are: {self.name}"]

        if aug.get("persona"):
            parts.append(f"Tone: {aug['persona'].get('tone', 'neutral')}")

        parts.append("\nIMPORTANT: Use exact figures, dates, and names from the provided knowledge. Do not round, approximate, or paraphrase numerical values. Cite precisely.")

        persona_constraints = self.files["persona"].get("constraints", [])
        if persona_constraints:
            parts.append("\nYou MUST follow these rules:")
            for c in persona_constraints:
                # Expand terse slugs into clear instructions
                expanded = c.replace("-", " ").strip()
                parts.append(f"- {expanded}")

        if aug.get("kb"):
            parts.append("\nKnowledge:")
            for kb in aug["kb"]:
                parts.append(f"- {kb[:200]}...")

        if aug.get("kg"):
            parts.append("\nReference Data (cite these exactly):")
            for node in aug["kg"]:
                # Use rdfs:label only - never expose @id to LLM (prevents AEC score inflation)
                label = node.get("rdfs:label")
                if not label:
                    continue  # Skip nodes without human-readable labels
                # Build a compact summary of key properties
                # Exclude: @-prefixed, namespaced keys (foo:bar), and values containing node IDs
                props = []
                for k, v in node.items():
                    # Skip JSON-LD keywords, rdfs:label, and any namespaced property (contains :)
                    if k.startswith("@") or k == "rdfs:label" or ":" in k:
                        continue
                    # Skip values that look like node IDs (contain namespace:id patterns)
                    v_str = str(v)
                    if ":" in v_str and any(ns in v_str for ns in ["aether:", "rule:", "antipattern:", "technique:", "concept:", "skill:", "psi:"]):
                        continue
                    if isinstance(v, (str, int, float, bool)):
                        props.append(f"{k}: {v}")
                    elif isinstance(v, list) and len(v) <= 5:
                        # Filter list items that look like node IDs
                        clean_items = [str(item) for item in v if ":" not in str(item)]
                        if clean_items:
                            props.append(f"{k}: {clean_items}")
                if props:
                    parts.append(f"- {label} ({'; '.join(props[:5])})")
                else:
                    parts.append(f"- {label}")

        parts.append(f"\nQuery: {ctx['input']}")

        # Add knowledge constraints if provided (for AEC retry)
        if constraints:
            parts.append("\nKNOWLEDGE CONSTRAINTS:")
            parts.append("The following claims are not supported by the knowledge base.")
            parts.append("Do not make these claims in your response:")
            for c in constraints:
                parts.append(f"- {c}")

        parts.append("\nResponse:")

        return "\n".join(parts)

    def generate(self, ctx: dict) -> dict:
        """Stage 3: Build prompt and call LLM."""
        prompt = self._build_prompt(ctx)
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
        """Stage 4: Verify response quality via AEC with retry on failure."""
        response = ctx["generated"]
        # Handle both dict and string from LLM
        if isinstance(response, dict):
            response_text = response.get("text", str(response))
        else:
            response_text = str(response)

        definition = self.files["definition"]
        kg_nodes = ctx["augmented"].get("kg", [])
        threshold = definition.get("review", {}).get("threshold", 0.8)

        # First run: AEC verification
        aec_result = aec_verify(response_text, kg_nodes, threshold,
                                compiled_kg=self._compiled_kg, llm_fn=self.llm_fn)

        # If passed on first try, return success
        if aec_result["passed"]:
            ctx["review"] = {
                "aec": aec_result,
                "passed": True,
                "queued": False,
                "self_corrected": False,
                "ghost": False,
            }
            return ctx

        # First run failed - always queue the original failure
        queue_failure(self.path, ctx["input"], response_text, aec_result)

        # Retry with constrained prompt
        gaps = [g["text"] for g in aec_result.get("gaps", [])]
        constrained_prompt = self._build_prompt(ctx, constraints=gaps)
        constrained_result = self.llm_fn(constrained_prompt)

        # Extract retry text
        if isinstance(constrained_result, dict):
            retry_text = constrained_result.get("text", str(constrained_result))
        else:
            retry_text = str(constrained_result)

        # Verify retry response
        retry_aec = aec_verify(retry_text, kg_nodes, threshold,
                               compiled_kg=self._compiled_kg, llm_fn=self.llm_fn)

        if retry_aec["passed"]:
            # Retry succeeded - update generated and return self_corrected
            ctx["generated"] = retry_text
            ctx["review"] = {
                "aec": retry_aec,
                "passed": True,
                "queued": True,
                "self_corrected": True,
                "ghost": False,
            }
            return ctx

        # Retry also failed - GHOST state
        ctx["generated"] = "[GHOST] Unable to verify response against knowledge base. Confidence: 0.0"
        ctx["review"] = {
            "aec": retry_aec,
            "passed": False,
            "queued": True,
            "self_corrected": False,
            "ghost": True,
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
