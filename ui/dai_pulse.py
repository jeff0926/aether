"""
DAI Pulse - Cognitive state machine for AETHER UI projection.

Emits CVP (CSS-Var Patch Protocol) events as JSON strings.
Transport-agnostic - caller handles SSE, WebSocket, or any stream.

Phases:
- discovery: Distill + Augment running
- deliberation: Generate running (LLM thinking)
- validation: Review/AEC running
- delivery: Pipeline complete, response ready
- ghost: AEC failed twice, response unverifiable
- alive: Heartbeat tick, no state change
- recovering: New query arriving after GHOST, before discovery
"""

import json
import time
import hashlib
from pathlib import Path

# Valid phase names
PHASES = ["discovery", "deliberation", "validation", "delivery", "ghost", "recovering", "alive"]

# Default pulse map (used if no custom map provided)
DEFAULT_PULSE_MAP = {
    "discovery": {
        "--kinetic-tempo": "400ms",
        "--kinetic-scale": "1.0",
        "--surface-accent": "#2196F3",
        "--surface-opacity": "0.85"
    },
    "deliberation": {
        "--kinetic-tempo": "200ms",
        "--kinetic-scale": "1.0",
        "--surface-accent": "#FF9800",
        "--surface-opacity": "0.90"
    },
    "validation": {
        "--kinetic-tempo": "100ms",
        "--kinetic-scale": "1.0",
        "--surface-accent": "#9C27B0",
        "--surface-opacity": "0.95"
    },
    "delivery": {
        "--kinetic-tempo": "0ms",
        "--kinetic-scale": "1.0",
        "--surface-accent": "#4CAF50",
        "--surface-opacity": "1.0"
    },
    "ghost": {
        "--kinetic-tempo": "600ms",
        "--kinetic-scale": "0.95",
        "--surface-accent": "#9E9E9E",
        "--surface-opacity": "0.60"
    },
    "recovering": {
        "--kinetic-tempo": "300ms",
        "--kinetic-scale": "1.0",
        "--surface-accent": "#2196F3",
        "--surface-opacity": "0.70"
    }
}


def _load_pulse_map(capsule_path: Path = None) -> dict:
    """
    Load pulse map with fallback chain:
    1. Capsule-specific pulse-map.json
    2. AETHER default pulse-map.default.json
    3. Hardcoded DEFAULT_PULSE_MAP
    """
    result = DEFAULT_PULSE_MAP.copy()

    # Try loading default from ui/ directory
    ui_dir = Path(__file__).parent
    default_path = ui_dir / "pulse-map.default.json"
    if default_path.exists():
        try:
            with open(default_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge phase by phase (skip metadata keys starting with _)
                for phase in PHASES:
                    if phase in data:
                        result[phase] = {**result.get(phase, {}), **data[phase]}
        except (json.JSONDecodeError, IOError):
            pass

    # Try loading capsule-specific override
    if capsule_path:
        capsule_map_path = Path(capsule_path) / "pulse-map.json"
        if capsule_map_path.exists():
            try:
                with open(capsule_map_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge: capsule map overrides per-key, not wholesale
                    for phase in PHASES:
                        if phase in data:
                            result[phase] = {**result.get(phase, {}), **data[phase]}
            except (json.JSONDecodeError, IOError):
                pass

    return result


class DAIPulse:
    """
    Cognitive state machine for AETHER UI projection.
    Emits CVP (CSS-Var Patch Protocol) events as JSON strings.
    Transport-agnostic - caller handles SSE, WebSocket, or any stream.
    """

    def __init__(
        self,
        capsule_id: str,
        scope: str = "document",
        pulse_map: dict = None,
        capsule_path: str | Path = None,
        heartbeat_interval: int = 20,
        ghost_threshold_multiplier: int = 3,
        min_phase_duration_ms: int = 200
    ):
        """
        Initialize DAI Pulse.

        Args:
            capsule_id: Identifier for the capsule (used in meta)
            scope: CSS selector or "document" for CSS variable scope
            pulse_map: Custom pulse map dict (overrides defaults)
            capsule_path: Path to capsule directory (for loading pulse-map.json)
            heartbeat_interval: Seconds between heartbeat events (default: 20)
            ghost_threshold_multiplier: Multiplier for GHOST timeout (default: 3)
            min_phase_duration_ms: Minimum display time per phase (default: 200ms)
        """
        self._capsule_id = capsule_id
        self._scope = scope
        self._heartbeat_interval = heartbeat_interval
        self._ghost_threshold_multiplier = ghost_threshold_multiplier
        self._min_phase_duration_ms = min_phase_duration_ms

        # Load pulse map with fallback chain
        self._pulse_map = _load_pulse_map(capsule_path)
        if pulse_map:
            # Override with provided pulse map
            for phase in PHASES:
                if phase in pulse_map:
                    self._pulse_map[phase] = {**self._pulse_map.get(phase, {}), **pulse_map[phase]}

        # State tracking
        self._current_phase = None
        self._sequence = 0
        self._phase_start_time = 0
        self._current_vars = {}  # Track current CSS state for reconnect

    @property
    def current_phase(self) -> str | None:
        """Current phase name."""
        return self._current_phase

    @property
    def sequence(self) -> int:
        """Current sequence number."""
        return self._sequence

    @property
    def ghost_threshold_ms(self) -> int:
        """GHOST timeout threshold in milliseconds."""
        return self._heartbeat_interval * self._ghost_threshold_multiplier * 1000

    def _generate_frame_id(self) -> str:
        """Generate unique frame ID."""
        data = f"{self._capsule_id}:{self._sequence}:{time.time()}"
        return f"frame-{hashlib.md5(data.encode()).hexdigest()[:12]}"

    def _enforce_min_duration(self) -> None:
        """Enforce minimum phase duration to prevent kinetic flicker."""
        if self._phase_start_time > 0:
            elapsed_ms = (time.time() - self._phase_start_time) * 1000
            remaining_ms = self._min_phase_duration_ms - elapsed_ms
            if remaining_ms > 0:
                time.sleep(remaining_ms / 1000)

    def _build_event(
        self,
        event_type: str,
        vars_dict: dict,
        phase: str,
        heartbeat: bool = False,
        reason: str = None
    ) -> str:
        """Build CVP event JSON string."""
        self._sequence += 1

        event = {
            "type": event_type,
            "id": self._generate_frame_id(),
            "ts": int(time.time() * 1000),
            "scope": self._scope,
            "vars": vars_dict,
            "meta": {
                "phase": phase,
                "capsule": self._capsule_id,
                "sequence": self._sequence,
                "heartbeat": heartbeat,
                "reason": reason
            }
        }

        return json.dumps(event, separators=(",", ":"))

    def transition(self, phase: str, reason: str = None) -> str:
        """
        Transition to a new phase and emit CVP event.

        Args:
            phase: Target phase name (must be in PHASES, excluding "alive")
            reason: Optional reason for the transition (e.g., "aec_failed_twice")

        Returns:
            CVP event JSON string

        Raises:
            ValueError: If phase is unknown or is "alive" (use heartbeat() instead)
        """
        if phase not in PHASES:
            raise ValueError(f"Unknown phase: {phase}. Valid phases: {PHASES}")

        if phase == "alive":
            raise ValueError("Use heartbeat() for alive phase, not transition()")

        # Enforce minimum phase duration for previous phase
        self._enforce_min_duration()

        # Update state
        self._current_phase = phase
        self._phase_start_time = time.time()

        # Get vars for this phase
        phase_vars = self._pulse_map.get(phase, {})

        # Update current vars state
        self._current_vars.update(phase_vars)

        return self._build_event(
            event_type="aether.css-delta",
            vars_dict=phase_vars,
            phase=phase,
            heartbeat=False,
            reason=reason
        )

    def heartbeat(self) -> str:
        """
        Emit heartbeat event with empty vars.

        Returns:
            CVP heartbeat event JSON string
        """
        return self._build_event(
            event_type="aether.css-delta",
            vars_dict={},
            phase=self._current_phase or "alive",
            heartbeat=True,
            reason=None
        )

    def reconnect(self) -> str:
        """
        Emit state-snapshot event for reconnection.
        Contains full current CSS state.

        Returns:
            CVP state-snapshot event JSON string
        """
        self._sequence += 1

        event = {
            "type": "aether.state-snapshot",
            "scope": self._scope,
            "vars": self._current_vars.copy(),
            "meta": {
                "phase": self._current_phase or "alive",
                "sequence": self._sequence
            }
        }

        return json.dumps(event, separators=(",", ":"))


if __name__ == "__main__":
    # Basic usage demonstration
    pulse = DAIPulse(capsule_id="test-agent", scope="document")

    print("=== DAI Pulse Demo ===\n")

    # Normal flow
    print("Discovery phase:")
    print(pulse.transition("discovery"))
    print()

    print("Deliberation phase:")
    print(pulse.transition("deliberation"))
    print()

    print("Validation phase:")
    print(pulse.transition("validation"))
    print()

    print("Delivery phase:")
    print(pulse.transition("delivery"))
    print()

    print("Heartbeat:")
    print(pulse.heartbeat())
    print()

    # GHOST flow
    print("GHOST phase (AEC failed twice):")
    print(pulse.transition("ghost", reason="aec_failed_twice"))
    print()

    print("Recovery phase (new query):")
    print(pulse.transition("recovering", reason="new_query"))
    print()

    # Reconnect snapshot
    print("Reconnect snapshot:")
    print(pulse.reconnect())
    print()

    print(f"Final sequence: {pulse.sequence}")
    print(f"Current phase: {pulse.current_phase}")
