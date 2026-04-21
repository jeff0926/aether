"""
agent_stamper.py - Main entry point for the AETHER Stamper Agent
Extracts normative assertions from source documents and produces verified capsules.

Usage:
    from stamper import AgentStamper
    stamper = AgentStamper()
    capsule_path = stamper.stamp("path/to/SKILL.md", "examples/")
"""

import json
import re
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from .pipeline import UniversalExtractor
from .kg_projection import nas_to_kg, verify_antipatterns, check_mvc, kg_stats


# ─────────────────────────────────────────────────────────────────────
# CAPSULE FILE TEMPLATES
# ─────────────────────────────────────────────────────────────────────

DEFAULT_DEFINITION = {
    "pipeline": {
        "distill": {"enabled": True},
        "augment": {"enabled": True},
        "generate": {"enabled": True},
        "review": {"enabled": True}
    },
    "review": {
        "min_length": 10,
        "max_length": 10000,
        "threshold": 0.8
    }
}

DEFAULT_PERSONA = {
    "tone": "neutral",
    "style": "informative",
    "constraints": []
}

DEFAULT_KB_HEADER = "# Knowledge Base\n\n"


# ─────────────────────────────────────────────────────────────────────
# ID GENERATION
# ─────────────────────────────────────────────────────────────────────

def generate_capsule_id(name: str, version: str = "1.0.0") -> str:
    """Generate capsule ID: {slug}-v{version}-{uid8}."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    raw = f"{name}:{version}:{datetime.now().isoformat()}"
    uid = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"{slug}-v{version}-{uid}"


# ─────────────────────────────────────────────────────────────────────
# AGENT STAMPER CLASS
# ─────────────────────────────────────────────────────────────────────

class AgentStamper:
    """
    Main stamper agent. Converts source documents into AETHER capsules.

    Pipeline:
    1. Extract content from source (any supported format)
    2. Classify into NAS assertions
    3. Project to KG nodes
    4. Write capsule files
    """

    def __init__(self, llm_fn: Callable = None):
        """
        Initialize stamper.

        Args:
            llm_fn: Optional LLM function for Layer 3 classification.
        """
        self.extractor = UniversalExtractor(llm_fn=llm_fn)

    def stamp(
        self,
        source_path: str | Path,
        output_dir: str | Path,
        name: str = None,
        version: str = "1.0.0"
    ) -> Path:
        """
        Create a new capsule from source document.

        Args:
            source_path: Path to source document (SKILL.md, .docx, etc.)
            output_dir: Directory to create capsule folder in
            name: Optional capsule name (defaults to source filename)
            version: Capsule version (default: 1.0.0)

        Returns:
            Path to created capsule folder

        Raises:
            ValueError: If extraction or validation fails
        """
        source_path = Path(source_path)
        output_dir = Path(output_dir)

        if not source_path.exists():
            raise FileNotFoundError(f"Source not found: {source_path}")

        # Default name from source filename
        if not name:
            name = source_path.stem.replace("SKILL", "skill").replace("_", "-")

        # Extract and classify
        nas_doc = self.extractor.extract(source_path)

        if nas_doc.get("status") == "error":
            raise ValueError(f"Extraction failed: {nas_doc['error_code']}: {nas_doc['message']}")

        # Validate NAS document
        validation = nas_doc.get("validation", {})
        if not validation.get("valid", False):
            errors = validation.get("errors", [])
            if errors:
                raise ValueError(f"Validation failed: {errors}")

        # Project to KG
        kg = nas_to_kg(nas_doc)

        # Run MVC validation (tiered: errors vs warnings)
        mvc_result = check_mvc(kg)

        # Hard fails block capsule creation
        if not mvc_result["valid"]:
            error_msgs = [e["message"] for e in mvc_result["errors"]]
            raise ValueError(f"MVC validation failed: {'; '.join(error_msgs)}")

        # Warnings are printed but don't block
        if mvc_result["warnings"]:
            print(f"MVC warnings: {len(mvc_result['warnings'])} issues")
            for w in mvc_result["warnings"]:
                print(f"  [{w['code']}] {w['message']}")

        # Create capsule
        capsule_path = self._create_capsule(
            name=name,
            version=version,
            output_dir=output_dir,
            source_path=source_path,
            nas_doc=nas_doc,
            kg=kg
        )

        return capsule_path

    def _create_capsule(
        self,
        name: str,
        version: str,
        output_dir: Path,
        source_path: Path,
        nas_doc: dict,
        kg: dict
    ) -> Path:
        """Create the 5-file capsule structure."""
        capsule_id = generate_capsule_id(name, version)
        capsule_path = output_dir / capsule_id
        capsule_path.mkdir(parents=True, exist_ok=True)

        prefix = capsule_id

        # 1. Manifest
        manifest = {
            "id": capsule_id,
            "name": name,
            "version": version,
            "created": datetime.now().isoformat(),
            "source": {
                "document": source_path.name,
                "format": source_path.suffix.lstrip('.'),
                "assertions_extracted": nas_doc.get("extraction", {}).get("total_assertions", 0)
            },
            "stamper_version": "1.0.0"
        }
        self._write_json(capsule_path / f"{prefix}-manifest.json", manifest)

        # 2. Definition
        self._write_json(capsule_path / f"{prefix}-definition.json", DEFAULT_DEFINITION)

        # 3. Persona (extract from frontmatter if available)
        persona = self._extract_persona(nas_doc)
        self._write_json(capsule_path / f"{prefix}-persona.json", persona)

        # 4. KB (source text)
        kb_content = self._build_kb(source_path, nas_doc)
        (capsule_path / f"{prefix}-kb.md").write_text(kb_content, encoding="utf-8")

        # 5. KG
        self._write_json(capsule_path / f"{prefix}-kg.jsonld", kg)

        return capsule_path

    def _extract_persona(self, nas_doc: dict) -> dict:
        """Extract persona from NAS document frontmatter."""
        # Try to get from source frontmatter
        # For now, use defaults
        return DEFAULT_PERSONA.copy()

    def _build_kb(self, source_path: Path, nas_doc: dict) -> str:
        """Build KB content from source document."""
        try:
            content = source_path.read_text(encoding="utf-8")

            # For markdown, strip YAML frontmatter
            if source_path.suffix.lower() == ".md":
                content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

            return content

        except Exception:
            return DEFAULT_KB_HEADER + "<!-- Source content could not be read -->\n"

    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON file with pretty printing."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def restamp(
        self,
        capsule_path: str | Path,
        source_path: str | Path,
        new_version: str
    ) -> Path:
        """
        Re-stamp an existing capsule with new version from updated source.

        Preserves lineage by recording previous_id and previous_version.
        """
        capsule_path = Path(capsule_path)
        source_path = Path(source_path)

        # Load existing manifest
        manifest_files = list(capsule_path.glob("*-manifest.json"))
        if not manifest_files:
            raise ValueError(f"No manifest found in {capsule_path}")

        old_manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
        name = old_manifest.get("name", capsule_path.name.split("-v")[0])

        # Create new capsule
        new_capsule = self.stamp(
            source_path=source_path,
            output_dir=capsule_path.parent,
            name=name,
            version=new_version
        )

        # Update manifest with lineage
        new_manifest_path = list(new_capsule.glob("*-manifest.json"))[0]
        new_manifest = json.loads(new_manifest_path.read_text(encoding="utf-8"))
        new_manifest["previous_id"] = old_manifest["id"]
        new_manifest["previous_version"] = old_manifest["version"]
        new_manifest["restamped"] = datetime.now().isoformat()
        self._write_json(new_manifest_path, new_manifest)

        return new_capsule

    def get_stats(self) -> dict:
        """Return extraction and classification statistics."""
        return self.extractor.get_stats()


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m stamper.agent_stamper <source_file> <output_dir> [name] [version]")
        print("\nExample:")
        print("  python -m stamper.agent_stamper SKILL.md examples/ docx-skill 1.0.0")
        sys.exit(1)

    source_path = sys.argv[1]
    output_dir = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else None
    version = sys.argv[4] if len(sys.argv) > 4 else "1.0.0"

    stamper = AgentStamper()

    try:
        capsule_path = stamper.stamp(source_path, output_dir, name, version)
        print(f"Created capsule: {capsule_path}")
        print(f"Classifier stats: {stamper.get_stats()}")

        # Print KG stats
        kg_path = list(capsule_path.glob("*-kg.jsonld"))[0]
        kg = json.loads(kg_path.read_text(encoding="utf-8"))
        stats = kg_stats(kg)
        print(f"KG nodes: {stats['total_nodes']}")
        print(f"By type: {stats['by_type']}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
