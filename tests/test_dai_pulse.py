"""
Tests for DAI Pulse - Cognitive state machine for AETHER UI projection.
"""

import json
import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.dai_pulse import DAIPulse, PHASES


def check(name: str, condition: bool, details: str = ""):
    """Test helper - prints PASS/FAIL."""
    status = "PASS" if condition else "FAIL"
    msg = f"  {status}: {name}"
    if details:
        msg += f" ({details})"
    print(msg)
    return condition


def test_phase_transitions():
    """Test that phase transitions produce correct CVP JSON."""
    print("\nTest 1: Phase transitions produce correct CVP JSON")

    pulse = DAIPulse(capsule_id="test-capsule", scope="document", min_phase_duration_ms=0)

    # Test discovery phase
    event_json = pulse.transition("discovery")
    event = json.loads(event_json)

    check("event type is aether.css-delta", event["type"] == "aether.css-delta")
    check("scope is document", event["scope"] == "document")
    check("meta.phase is discovery", event["meta"]["phase"] == "discovery")
    check("meta.capsule is test-capsule", event["meta"]["capsule"] == "test-capsule")
    check("meta.heartbeat is False", event["meta"]["heartbeat"] is False)
    check("vars contains --kinetic-tempo", "--kinetic-tempo" in event["vars"])
    check("vars contains --surface-accent", "--surface-accent" in event["vars"])

    # Test deliberation phase
    event_json = pulse.transition("deliberation")
    event = json.loads(event_json)
    check("deliberation phase vars has orange accent",
         event["vars"]["--surface-accent"] == "#FF9800")


def test_sequence_increments():
    """Test that sequence numbers increment correctly."""
    print("\nTest 2: Sequence numbers increment correctly")

    pulse = DAIPulse(capsule_id="test-seq", min_phase_duration_ms=0)

    check("initial sequence is 0", pulse.sequence == 0)

    pulse.transition("discovery")
    check("sequence after first transition is 1", pulse.sequence == 1)

    pulse.transition("deliberation")
    check("sequence after second transition is 2", pulse.sequence == 2)

    pulse.heartbeat()
    check("sequence after heartbeat is 3", pulse.sequence == 3)

    pulse.reconnect()
    check("sequence after reconnect is 4", pulse.sequence == 4)


def test_heartbeat_empty_vars():
    """Test that heartbeat produces correct event with empty vars."""
    print("\nTest 3: Heartbeat produces correct event with empty vars")

    pulse = DAIPulse(capsule_id="test-hb", min_phase_duration_ms=0)
    pulse.transition("deliberation")

    hb_json = pulse.heartbeat()
    hb = json.loads(hb_json)

    check("heartbeat type is aether.css-delta", hb["type"] == "aether.css-delta")
    check("heartbeat vars is empty dict", hb["vars"] == {})
    check("meta.heartbeat is True", hb["meta"]["heartbeat"] is True)
    check("meta.phase is current phase", hb["meta"]["phase"] == "deliberation")


def test_reconnect_state_snapshot():
    """Test that state snapshot on reconnect contains full current state."""
    print("\nTest 4: State snapshot on reconnect contains full current state")

    pulse = DAIPulse(capsule_id="test-snap", min_phase_duration_ms=0)

    # Go through several phases to accumulate state
    pulse.transition("discovery")
    pulse.transition("deliberation")
    pulse.transition("validation")

    snap_json = pulse.reconnect()
    snap = json.loads(snap_json)

    check("snapshot type is aether.state-snapshot", snap["type"] == "aether.state-snapshot")
    check("snapshot has scope", snap["scope"] == "document")
    check("snapshot vars is not empty", len(snap["vars"]) > 0)
    check("snapshot meta.phase is validation", snap["meta"]["phase"] == "validation")
    check("snapshot has sequence", "sequence" in snap["meta"])


def test_ghost_transition_reason():
    """Test that GHOST transition includes reason field."""
    print("\nTest 5: GHOST transition includes reason field")

    pulse = DAIPulse(capsule_id="test-ghost", min_phase_duration_ms=0)
    pulse.transition("validation")

    ghost_json = pulse.transition("ghost", reason="aec_failed_twice")
    ghost = json.loads(ghost_json)

    check("ghost phase is set", ghost["meta"]["phase"] == "ghost")
    check("reason is aec_failed_twice", ghost["meta"]["reason"] == "aec_failed_twice")
    check("ghost vars has gray accent", ghost["vars"]["--surface-accent"] == "#9E9E9E")
    check("ghost vars has reduced opacity", ghost["vars"]["--surface-opacity"] == "0.60")


def test_recovery_transition():
    """Test that recovery transition works after GHOST."""
    print("\nTest 6: Recovery transition clears ghost state")

    pulse = DAIPulse(capsule_id="test-recover", min_phase_duration_ms=0)
    pulse.transition("ghost", reason="aec_failed_twice")

    recover_json = pulse.transition("recovering", reason="new_query")
    recover = json.loads(recover_json)

    check("phase is recovering", recover["meta"]["phase"] == "recovering")
    check("reason is new_query", recover["meta"]["reason"] == "new_query")
    check("current_phase property is recovering", pulse.current_phase == "recovering")


def test_unknown_phase_raises():
    """Test that unknown phase name raises ValueError."""
    print("\nTest 7: Unknown phase name raises ValueError")

    pulse = DAIPulse(capsule_id="test-unknown", min_phase_duration_ms=0)

    raised = False
    try:
        pulse.transition("invalid_phase")
    except ValueError as e:
        raised = True
        check("ValueError raised", True)
        check("error mentions invalid phase", "invalid_phase" in str(e))

    if not raised:
        check("ValueError raised", False)


def test_alive_phase_blocked():
    """Test that 'alive' phase cannot be used with transition()."""
    print("\nTest 8: 'alive' phase blocked from transition()")

    pulse = DAIPulse(capsule_id="test-alive", min_phase_duration_ms=0)

    raised = False
    try:
        pulse.transition("alive")
    except ValueError as e:
        raised = True
        check("ValueError raised for alive", True)
        check("error mentions heartbeat()", "heartbeat()" in str(e))

    if not raised:
        check("ValueError raised for alive", False)


def test_min_phase_duration():
    """Test that minimum phase duration is enforced."""
    print("\nTest 9: Minimum phase duration is enforced")

    # Use a 100ms minimum for testing
    pulse = DAIPulse(capsule_id="test-duration", min_phase_duration_ms=100)

    start = time.time()
    pulse.transition("discovery")
    pulse.transition("deliberation")  # This should wait ~100ms
    elapsed = (time.time() - start) * 1000

    check("elapsed time >= 100ms", elapsed >= 100, f"{elapsed:.1f}ms")
    check("elapsed time < 300ms (not too long)", elapsed < 300, f"{elapsed:.1f}ms")


def test_event_id_format():
    """Test that event IDs have correct format."""
    print("\nTest 10: Event ID format is correct")

    pulse = DAIPulse(capsule_id="test-id", min_phase_duration_ms=0)

    event_json = pulse.transition("discovery")
    event = json.loads(event_json)

    check("id starts with 'frame-'", event["id"].startswith("frame-"))
    check("id has hash suffix", len(event["id"]) > 6)  # "frame-" + hash


def test_timestamp_present():
    """Test that timestamp is present and reasonable."""
    print("\nTest 11: Timestamp is present and reasonable")

    pulse = DAIPulse(capsule_id="test-ts", min_phase_duration_ms=0)

    before = int(time.time() * 1000)
    event_json = pulse.transition("discovery")
    after = int(time.time() * 1000)

    event = json.loads(event_json)

    check("ts is present", "ts" in event)
    check("ts is within range", before <= event["ts"] <= after)


def test_custom_pulse_map():
    """Test that custom pulse map overrides defaults."""
    print("\nTest 12: Custom pulse map overrides defaults")

    custom_map = {
        "discovery": {
            "--surface-accent": "#CUSTOM_COLOR"
        }
    }

    pulse = DAIPulse(
        capsule_id="test-custom",
        pulse_map=custom_map,
        min_phase_duration_ms=0
    )

    event_json = pulse.transition("discovery")
    event = json.loads(event_json)

    check("custom accent applied", event["vars"]["--surface-accent"] == "#CUSTOM_COLOR")
    # Other vars should still be present from defaults
    check("default kinetic-tempo preserved", "--kinetic-tempo" in event["vars"])


def test_all_phases_have_vars():
    """Test that all valid phases have CSS variables defined."""
    print("\nTest 13: All valid phases have CSS variables")

    pulse = DAIPulse(capsule_id="test-all", min_phase_duration_ms=0)

    for phase in ["discovery", "deliberation", "validation", "delivery", "ghost", "recovering"]:
        event_json = pulse.transition(phase)
        event = json.loads(event_json)
        check(f"{phase} has vars", len(event["vars"]) > 0)


if __name__ == "__main__":
    print("=" * 60)
    print("DAI Pulse Test Suite")
    print("=" * 60)

    test_phase_transitions()
    test_sequence_increments()
    test_heartbeat_empty_vars()
    test_reconnect_state_snapshot()
    test_ghost_transition_reason()
    test_recovery_transition()
    test_unknown_phase_raises()
    test_alive_phase_blocked()
    test_min_phase_duration()
    test_event_id_format()
    test_timestamp_present()
    test_custom_pulse_map()
    test_all_phases_have_vars()

    print("\n" + "=" * 60)
    print("All DAI Pulse tests completed!")
    print("=" * 60)
