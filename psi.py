"""
AETHER PSI Layer - Server-side CSS Stream emission.
Emits JSON-over-SSE payloads conforming to the CVP (CSS Variable Patch) protocol.

The PSI layer projects agent cognitive state as CSS variables that transform
HTML fragments in real-time. Pipeline stages map to visual phases:
  - Distill    -> reflex       (quick pattern match)
  - Augment    -> deliberation (gathering context)
  - Generate   -> deliberation (producing response)
  - Review     -> complete     (AEC passed) or ghost (AEC failed)
"""

import json
import time

# Valid pipeline phases
PHASES = {"reflex", "deliberation", "complete", "ghost"}

# Security allowlist - only these CSS variables can be emitted
CSS_ALLOWLIST = {
    "--aether-state",
    "--aether-view-complexity",
    "--aether-sentiment",
    "--aether-density",
    "--aether-confidence",
}

# Semantic values for reference (not enforced, just documented)
AETHER_CSS_VARS = {
    "--aether-state": ["reflex", "deliberation", "complete", "ghost"],
    "--aether-view-complexity": "float 0.0-1.0",
    "--aether-sentiment": ["positive", "neutral", "negative", "critical"],
    "--aether-density": ["sparse", "standard", "dense"],
    "--aether-confidence": "float 0.0-1.0",
}


def validate_css_vars(vars_dict: dict) -> dict:
    """Strip any CSS variable not in the allowlist. Security gate."""
    return {k: v for k, v in vars_dict.items() if k in CSS_ALLOWLIST}


class AetherEmitter:
    """
    Emits CSS Variable Patch (CVP) events as SSE-formatted strings.
    Maintains state cache for reconnection snapshot replay.

    Usage:
        emitter = AetherEmitter("frontend-design", scope="#aether-frontend-design")
        event = emitter.pulse("deliberation", {"--aether-view-complexity": "0.5"})
        yield event  # Send via SSE StreamingResponse
    """

    def __init__(self, agent_id: str, scope: str = None):
        """
        Initialize emitter for an agent.

        Args:
            agent_id: Unique agent identifier
            scope: CSS selector for target element (default: #aether-{agent_id})
        """
        self.agent_id = agent_id
        self.scope = scope or f"#aether-{agent_id}"
        self.state_cache = {}       # Current CSS variable state
        self.content_cache = None   # Current text content
        self.sequence = 0           # Monotonic counter for ordering
        self.current_phase = "reflex"

    def pulse(self, phase: str, css_vars: dict = None, content: str = None,
              aec_score: float = None, reason: str = None) -> str:
        """
        Emit a single CVP event as SSE-formatted string.

        Args:
            phase: reflex | deliberation | complete | ghost
            css_vars: CSS variable mutations (filtered through allowlist)
            content: Text content for slot injection
            aec_score: AEC verification score (on complete/ghost)
            reason: Failure reason (on ghost)

        Returns:
            SSE-formatted string ready for streaming
        """
        if phase not in PHASES:
            phase = "deliberation"

        self.current_phase = phase
        self.sequence += 1

        # Filter through allowlist
        safe_vars = {}
        if css_vars:
            safe_vars = {k: v for k, v in css_vars.items() if k in CSS_ALLOWLIST}
            self.state_cache.update(safe_vars)

        # Always include state variable
        safe_vars["--aether-state"] = phase
        self.state_cache["--aether-state"] = phase

        if content is not None:
            self.content_cache = content

        payload = {
            "type": "aether.css-delta",
            "id": f"frame-{self.sequence:05d}",
            "ts": int(time.time() * 1000),
            "scope": self.scope,
            "phase": phase,
            "vars": safe_vars,
            "content": content,
            "meta": {
                "agent": self.agent_id,
                "sequence": self.sequence,
                "aec_score": aec_score,
                "reason": reason,
            }
        }

        return f"event: aether.css-delta\ndata: {json.dumps(payload)}\n\n"

    def snapshot(self) -> str:
        """
        Emit full state snapshot for reconnection.
        Client receives complete current state in one payload.
        """
        self.sequence += 1
        payload = {
            "type": "aether.css-delta",
            "id": f"snapshot-{self.sequence:05d}",
            "ts": int(time.time() * 1000),
            "scope": self.scope,
            "phase": self.current_phase,
            "vars": self.state_cache.copy(),
            "content": self.content_cache,
            "meta": {
                "agent": self.agent_id,
                "sequence": self.sequence,
                "snapshot": True,
            }
        }
        return f"event: aether.css-delta\ndata: {json.dumps(payload)}\n\n"

    def heartbeat(self) -> str:
        """
        Emit alive signal with current state.
        Configurable interval via definition.json heartbeat_interval_s.
        """
        return self.pulse(self.current_phase)

    def reset(self) -> None:
        """Reset emitter state for new session."""
        self.state_cache = {}
        self.content_cache = None
        self.sequence = 0
        self.current_phase = "reflex"


def pipeline_to_psi(capsule_result: dict, emitter: AetherEmitter) -> list:
    """
    Convert a pipeline result dict to a sequence of CVP events.
    Maps pipeline stages to PSI phases.

    Args:
        capsule_result: The dict returned by Capsule.run()
        emitter: AetherEmitter instance for this agent

    Returns:
        List of SSE-formatted strings
    """
    events = []

    # Phase 1: Reflex (Distill complete)
    events.append(emitter.pulse(
        phase="reflex",
        css_vars={
            "--aether-view-complexity": "0.2",
            "--aether-confidence": "0",
        }
    ))

    # Phase 2: Deliberation (Augment + Generate)
    events.append(emitter.pulse(
        phase="deliberation",
        css_vars={
            "--aether-view-complexity": "0.5",
        }
    ))

    # Phase 3: Complete or Ghost (Review)
    review = capsule_result.get("review", {})
    aec_data = review.get("aec", {})
    aec_score = aec_data.get("score", review.get("score", 0))
    aec_passed = review.get("passed", False)
    is_ghost = review.get("ghost", False)
    response = capsule_result.get("generated", "")

    if aec_passed and not is_ghost:
        events.append(emitter.pulse(
            phase="complete",
            css_vars={
                "--aether-view-complexity": "1.0",
                "--aether-confidence": str(round(aec_score, 2)),
                "--aether-sentiment": _detect_sentiment(response),
            },
            content=response,
            aec_score=aec_score,
        ))
    else:
        events.append(emitter.pulse(
            phase="ghost",
            css_vars={
                "--aether-view-complexity": "0.1",
                "--aether-confidence": "0",
                "--aether-sentiment": "negative",
            },
            content=None,
            aec_score=aec_score,
            reason=f"AEC score {aec_score:.2f} below threshold" if aec_score else "Verification failed",
        ))

    return events


def _detect_sentiment(text: str) -> str:
    """
    Lightweight keyword-based sentiment detection.
    Not LLM-powered - fast, deterministic, good enough for CSS projection.

    Returns: positive | neutral | negative | critical
    """
    if not text:
        return "neutral"

    text_lower = text.lower()

    critical_signals = ["critical", "severe", "fatal", "emergency", "breach", "violation"]
    negative_signals = ["error", "fail", "warning", "danger", "reject", "problem", "issue", "cannot", "unable"]
    positive_signals = ["success", "complete", "approved", "verified", "excellent", "great", "correct", "valid"]

    crit_count = sum(1 for w in critical_signals if w in text_lower)
    neg_count = sum(1 for w in negative_signals if w in text_lower)
    pos_count = sum(1 for w in positive_signals if w in text_lower)

    if crit_count > 0:
        return "critical"
    if neg_count > pos_count:
        return "negative"
    if pos_count > neg_count:
        return "positive"
    return "neutral"


# -----------------------------------------------------------------------------
# CLI Test
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== PSI Layer Tests ===\n")

    # Test 1: Basic emission
    print("Test 1: AetherEmitter basic pulse")
    e = AetherEmitter("test-agent", "#aether-test")
    event = e.pulse("reflex", {"--aether-view-complexity": "0.2"})
    print(event)

    # Test 2: State cache
    print("Test 2: State cache accumulation")
    e.pulse("reflex", {"--aether-view-complexity": "0.2"})
    e.pulse("deliberation", {"--aether-confidence": "0.5"})
    e.pulse("complete", {"--aether-sentiment": "positive"})
    print(f"State cache: {e.state_cache}")

    # Test 3: Snapshot
    print("\nTest 3: Snapshot for reconnection")
    snapshot = e.snapshot()
    print(snapshot)

    # Test 4: CSS allowlist security
    print("Test 4: CSS allowlist security")
    e2 = AetherEmitter("secure-test", "#test")
    event = e2.pulse("complete", {
        "--aether-confidence": "0.9",
        "--evil-var": "url(javascript:alert(1))",
        "--another-bad": "expression(evil)",
    })
    # Parse the event to verify filtering
    data_line = [l for l in event.split('\n') if l.startswith('data:')][0]
    payload = json.loads(data_line.replace('data: ', ''))
    print(f"Vars emitted: {list(payload['vars'].keys())}")
    assert "--evil-var" not in payload["vars"], "Security: evil var should be filtered"
    assert "--another-bad" not in payload["vars"], "Security: bad var should be filtered"
    print("PASS: Malicious CSS variables filtered\n")

    # Test 5: Sentiment detection
    print("Test 5: Sentiment detection")
    tests = [
        ("The operation completed successfully.", "positive"),
        ("Error: Unable to process request.", "negative"),
        ("Critical security breach detected!", "critical"),
        ("The weather is nice today.", "neutral"),
    ]
    for text, expected in tests:
        result = _detect_sentiment(text)
        status = "PASS" if result == expected else "FAIL"
        print(f"  [{status}] '{text[:40]}...' -> {result} (expected {expected})")

    # Test 6: Pipeline to PSI
    print("\nTest 6: Pipeline to PSI conversion")
    mock_result = {
        "generated": "Jefferson was born in 1743.",
        "review": {
            "passed": True,
            "ghost": False,
            "aec": {"score": 0.85},
        }
    }
    e3 = AetherEmitter("pipeline-test")
    events = pipeline_to_psi(mock_result, e3)
    print(f"Generated {len(events)} events")
    for i, ev in enumerate(events):
        lines = ev.strip().split('\n')
        data = json.loads(lines[1].replace('data: ', ''))
        print(f"  Event {i+1}: phase={data['phase']}, complexity={data['vars'].get('--aether-view-complexity', 'N/A')}")

    print("\n=== All PSI Tests Complete ===")
