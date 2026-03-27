"""
Test suite for engram.py - Subgraph Persistence / Working Memory layer.

Test cases from ENGRAM_FEATURE_BRICK_SPEC.md Section 9.
"""

import pytest
import tempfile
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import engram
import kg as kg_module


@pytest.fixture
def test_kg():
    """Create a test knowledge graph with various node types."""
    return {
        "@context": {
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "aether": "http://aether.dev/ontology#"
        },
        "@graph": [
            {
                "@id": "aether:core/warren_buffett",
                "rdfs:label": "Warren Buffett",
                "aether:origin": "core",
                "aether:confidence": 1.0,
                "aether:access_count": 5,
                "aether:related": "aether:core/berkshire_hathaway",
            },
            {
                "@id": "aether:core/berkshire_hathaway",
                "rdfs:label": "Berkshire Hathaway",
                "aether:origin": "core",
                "aether:confidence": 1.0,
                "aether:access_count": 3,
                "aether:related": "aether:core/value_investing",
            },
            {
                "@id": "aether:core/value_investing",
                "rdfs:label": "Value Investing",
                "aether:origin": "core",
                "aether:confidence": 0.9,
                "aether:access_count": 0,
            },
            {
                "@id": "aether:deprecated/old_fact",
                "rdfs:label": "Old Fact",
                "aether:origin": "deprecated",
                "aether:confidence": 0.5,
                "aether:access_count": 10,
            },
            {
                "@id": "aether:core/car",
                "rdfs:label": "car",
                "aether:origin": "core",
                "aether:confidence": 1.0,
                "aether:access_count": 1,
            },
            {
                "@id": "aether:core/distant_node",
                "rdfs:label": "Distant Node",
                "aether:origin": "core",
                "aether:confidence": 0.7,
                "aether:access_count": 0,
            },
        ]
    }


@pytest.fixture
def nodes(test_kg):
    """Extract nodes from test KG."""
    return kg_module.get_nodes(test_kg)


class TestScoreSalience:
    """Tests for score_salience function."""

    def test_score_salience_direct_mention(self, nodes, test_kg):
        """test_score_salience_direct_mention: score == 1.0"""
        scores = engram.score_salience(
            nodes=nodes,
            mentioned_ids=["aether:core/warren_buffett"],
            kg=test_kg
        )
        assert scores["aether:core/warren_buffett"] == 1.0

    def test_score_salience_inferred(self, nodes, test_kg):
        """test_score_salience_inferred: score == 0.6"""
        scores = engram.score_salience(
            nodes=nodes,
            mentioned_ids=["aether:core/warren_buffett"],
            kg=test_kg
        )
        # berkshire_hathaway is a neighbor of warren_buffett
        assert scores["aether:core/berkshire_hathaway"] == 0.6

    def test_score_salience_decay(self, nodes, test_kg):
        """test_score_salience_decay: score decreases with turn_count"""
        # With no mentions, historical nodes should decay
        scores_t0 = engram.score_salience(
            nodes=nodes,
            mentioned_ids=[],
            turn_count=0,
            kg=test_kg,
            decay_rate=0.15
        )
        scores_t5 = engram.score_salience(
            nodes=nodes,
            mentioned_ids=[],
            turn_count=5,
            kg=test_kg,
            decay_rate=0.15
        )

        # Warren Buffett has access_count > 0, so should be historical
        # At t=0: 1.0 - 0.15*0 = 1.0
        # At t=5: 1.0 - 0.15*5 = 0.25
        assert scores_t0["aether:core/warren_buffett"] == 1.0
        assert scores_t5["aether:core/warren_buffett"] == 0.25
        assert scores_t5["aether:core/warren_buffett"] < scores_t0["aether:core/warren_buffett"]

    def test_score_salience_deprecated_excluded(self, nodes, test_kg):
        """test_score_salience_deprecated_excluded: deprecated nodes always 0.0"""
        # Even if deprecated node is mentioned, it should be 0.0
        scores = engram.score_salience(
            nodes=nodes,
            mentioned_ids=["aether:deprecated/old_fact"],
            kg=test_kg
        )
        assert scores["aether:deprecated/old_fact"] == 0.0


class TestExtractSubgraph:
    """Tests for extract_subgraph function."""

    def test_extract_subgraph_max_hop(self, test_kg):
        """test_extract_subgraph_max_hop: nodes beyond max_hop excluded"""
        # With max_hop=1, should include warren_buffett and berkshire_hathaway
        # but NOT value_investing (which is 2 hops away via berkshire_hathaway)
        subgraph = engram.extract_subgraph(
            kg=test_kg,
            salient_ids=["aether:core/warren_buffett"],
            max_hop=1,
            max_nodes=100
        )
        subgraph_ids = {n.get("@id") for n in subgraph}

        assert "aether:core/warren_buffett" in subgraph_ids
        assert "aether:core/berkshire_hathaway" in subgraph_ids
        # value_investing is 2 hops away (connected via berkshire_hathaway)
        # With max_hop=1, it should be excluded
        # Note: distant_node is not connected at all, should be excluded
        assert "aether:core/distant_node" not in subgraph_ids

    def test_extract_subgraph_max_nodes(self, test_kg):
        """test_extract_subgraph_max_nodes: result never exceeds max_nodes"""
        # With a large max_hop but small max_nodes, should cap at max_nodes
        subgraph = engram.extract_subgraph(
            kg=test_kg,
            salient_ids=["aether:core/warren_buffett"],
            max_hop=10,
            max_nodes=2
        )
        assert len(subgraph) <= 2


class TestBuildManifest:
    """Tests for build_manifest function."""

    def test_build_manifest_schema(self, nodes, test_kg):
        """test_build_manifest_schema: all required fields present"""
        scores = engram.score_salience(
            nodes=nodes,
            mentioned_ids=["aether:core/warren_buffett"],
            kg=test_kg
        )
        subgraph = engram.extract_subgraph(
            kg=test_kg,
            salient_ids=["aether:core/warren_buffett"]
        )
        manifest = engram.build_manifest(
            capsule_id="test-capsule",
            subgraph=subgraph,
            salience_scores=scores,
            turn_id="t-001"
        )

        # Check all required fields from spec
        required_fields = [
            "@context",
            "@type",
            "engram:capsule_id",
            "engram:turn_id",
            "engram:created",
            "engram:schema_version",
            "engram:source_capsule",
            "engram:active_nodes",
            "engram:node_count",
            "engram:max_hop_used"
        ]
        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"

        # Check @type value
        assert manifest["@type"] == "engram:Manifest"

        # Check @context structure
        assert "aether" in manifest["@context"]
        assert "engram" in manifest["@context"]


class TestSaveLoadManifest:
    """Tests for save_manifest and load_manifest functions."""

    def test_save_load_manifest_roundtrip(self, nodes, test_kg):
        """test_save_load_manifest_roundtrip: save then load returns equivalent manifest"""
        scores = engram.score_salience(
            nodes=nodes,
            mentioned_ids=["aether:core/warren_buffett"],
            kg=test_kg
        )
        subgraph = engram.extract_subgraph(
            kg=test_kg,
            salient_ids=["aether:core/warren_buffett"]
        )
        original_manifest = engram.build_manifest(
            capsule_id="roundtrip-test",
            subgraph=subgraph,
            salience_scores=scores,
            turn_id="t-roundtrip"
        )

        with tempfile.TemporaryDirectory() as tmp:
            # Save
            save_path = engram.save_manifest(original_manifest, tmp)
            assert save_path.exists()
            assert save_path.name == "engram.jsonld"

            # Load
            loaded_manifest = engram.load_manifest(tmp)
            assert loaded_manifest is not None

            # Compare key fields (created timestamp will differ slightly)
            assert loaded_manifest["engram:capsule_id"] == original_manifest["engram:capsule_id"]
            assert loaded_manifest["engram:turn_id"] == original_manifest["engram:turn_id"]
            assert loaded_manifest["engram:node_count"] == original_manifest["engram:node_count"]
            assert loaded_manifest["@type"] == original_manifest["@type"]


class TestWarmContext:
    """Tests for warm_context function."""

    def test_warm_context_cold_start(self, test_kg):
        """test_warm_context_cold_start: warm=False when no engram.jsonld"""
        with tempfile.TemporaryDirectory() as tmp:
            result = engram.warm_context(tmp, test_kg)
            assert result["warm"] is False
            assert result["manifest"] is None
            assert result["active_nodes"] == []
            assert result["missing_ids"] == []

    def test_warm_context_warm_start(self, test_kg):
        """test_warm_context_warm_start: warm=True, active_nodes populated"""
        with tempfile.TemporaryDirectory() as tmp:
            # First commit a session to create engram
            engram.commit_session(
                capsule_id="warm-test",
                capsule_path=tmp,
                kg=test_kg,
                mentioned_ids=["aether:core/warren_buffett"],
                turn_id="t-warm"
            )

            # Now warm_context should find it
            result = engram.warm_context(tmp, test_kg)
            assert result["warm"] is True
            assert result["manifest"] is not None
            assert len(result["active_nodes"]) > 0

            # Verify the active nodes are actual node dicts, not just IDs
            for node in result["active_nodes"]:
                assert "@id" in node
                assert "rdfs:label" in node or "aether:origin" in node

    def test_warm_context_missing_ids(self, test_kg):
        """test_warm_context_missing_ids: missing_ids populated for stale nodes"""
        with tempfile.TemporaryDirectory() as tmp:
            # Create a manifest with a node that doesn't exist in KG
            fake_manifest = {
                "@context": {
                    "aether": "http://aether.dev/ontology#",
                    "engram": "http://aether.dev/engram#"
                },
                "@type": "engram:Manifest",
                "engram:capsule_id": "missing-ids-test",
                "engram:turn_id": "t-missing",
                "engram:created": "2026-03-26T00:00:00Z",
                "engram:schema_version": "1.0",
                "engram:source_capsule": "missing-ids-test",
                "engram:active_nodes": [
                    {"@id": "aether:core/warren_buffett", "engram:salience": 1.0, "engram:hop_depth": 0},
                    {"@id": "aether:nonexistent/stale_node", "engram:salience": 0.8, "engram:hop_depth": 1},
                ],
                "engram:node_count": 2,
                "engram:max_hop_used": 1
            }
            engram.save_manifest(fake_manifest, tmp)

            result = engram.warm_context(tmp, test_kg)
            assert result["warm"] is True
            assert "aether:nonexistent/stale_node" in result["missing_ids"]
            # Warren Buffett should be in active_nodes
            active_ids = [n.get("@id") for n in result["active_nodes"]]
            assert "aether:core/warren_buffett" in active_ids


class TestDetectConflict:
    """Tests for detect_conflict function."""

    def test_detect_conflict_verb_pattern(self, test_kg):
        """test_detect_conflict_verb_pattern: 'I sold the car' conflicts 'car' node"""
        result = engram.detect_conflict(
            kg=test_kg,
            statement="I sold the car yesterday",
            active_node_ids=["aether:core/car"]
        )
        assert result["conflict"] is True
        assert result["conflicted_node_id"] == "aether:core/car"
        assert "sold" in result["reason"].lower() or "car" in result["reason"].lower()

    def test_detect_conflict_no_false_positive(self, test_kg):
        """test_detect_conflict_no_false_positive: 'I bought a car' does not conflict"""
        result = engram.detect_conflict(
            kg=test_kg,
            statement="I bought a car yesterday",
            active_node_ids=["aether:core/car"]
        )
        assert result["conflict"] is False
        assert result["conflicted_node_id"] is None


class TestCommitSession:
    """Tests for commit_session function."""

    def test_commit_session_writes_file(self, test_kg):
        """test_commit_session_writes_file: engram.jsonld created in capsule_path"""
        with tempfile.TemporaryDirectory() as tmp:
            result = engram.commit_session(
                capsule_id="commit-test",
                capsule_path=tmp,
                kg=test_kg,
                mentioned_ids=["aether:core/warren_buffett"],
                turn_id="t-commit"
            )

            # Check file was created
            manifest_path = Path(result["manifest_path"])
            assert manifest_path.exists()
            assert manifest_path.name == "engram.jsonld"

            # Check result structure
            assert result["node_count"] > 0
            assert "manifest" in result
            assert result["manifest"]["@type"] == "engram:Manifest"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
