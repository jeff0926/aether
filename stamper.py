"""
Stamper - Creates capsule folders from source material.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from aether import generate_id, get_required_files, REQUIRED_SUFFIXES

DEFAULT_DEFINITION = {
    "pipeline": {"distill": {"enabled": True}, "augment": {"enabled": True},
                 "generate": {"enabled": True}, "review": {"enabled": True}},
    "review": {"min_length": 10, "max_length": 10000, "threshold": 0.8},
}
DEFAULT_PERSONA = {"tone": "neutral", "style": "informative", "constraints": []}
DEFAULT_KB = "# Knowledge Base\n\n<!-- Add knowledge content here -->\n"
DEFAULT_KG = {
    "@context": {"rdfs": "http://www.w3.org/2000/01/rdf-schema#", "aether": "http://aether.dev/ontology#"},
    "@graph": [],
}


def _write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def stamp_empty(name: str, path: str | Path, version: str = "1.0.0") -> Path:
    """Create a new empty capsule folder with all 5 required files."""
    path = Path(path)
    capsule_id = generate_id(name, version)
    capsule_path = path / capsule_id
    capsule_path.mkdir(parents=True, exist_ok=True)

    # Files are prefixed with folder name: {folder-name}-{type}.{ext}
    prefix = capsule_id
    _write_json(capsule_path / f"{prefix}-manifest.json", {
        "id": capsule_id, "name": name, "version": version, "created": datetime.now().isoformat()
    })
    _write_json(capsule_path / f"{prefix}-definition.json", DEFAULT_DEFINITION)
    _write_json(capsule_path / f"{prefix}-persona.json", DEFAULT_PERSONA)
    (capsule_path / f"{prefix}-kb.md").write_text(DEFAULT_KB, encoding="utf-8")
    _write_json(capsule_path / f"{prefix}-kg.jsonld", DEFAULT_KG)

    return capsule_path


def stamp_from_source(name: str, source_path: str | Path, output_path: str | Path, version: str = "1.0.0") -> Path:
    """Create capsule from source file. .md→kb, .jsonld→kg, .json→kg or definition."""
    source_path, output_path = Path(source_path), Path(output_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source not found: {source_path}")

    capsule_path = stamp_empty(name, output_path, version)
    prefix = capsule_path.name  # Folder name is the prefix
    suffix = source_path.suffix.lower()
    content = source_path.read_text(encoding="utf-8")

    if suffix == ".md":
        (capsule_path / f"{prefix}-kb.md").write_text(content, encoding="utf-8")
    elif suffix == ".jsonld":
        _write_json(capsule_path / f"{prefix}-kg.jsonld", json.loads(content))
    elif suffix == ".json":
        data = json.loads(content)
        if "@graph" in data or "@context" in data or "@id" in data:
            _write_json(capsule_path / f"{prefix}-kg.jsonld", data)
        else:
            _write_json(capsule_path / f"{prefix}-definition.json", {**DEFAULT_DEFINITION, **data})

    return capsule_path


def validate_capsule(path: str | Path) -> dict:
    """Check folder has all required files and they parse correctly."""
    path = Path(path)
    result = {"valid": True, "missing": [], "errors": []}

    if not path.is_dir():
        return {"valid": False, "missing": [f"<folder>{s}" for s in REQUIRED_SUFFIXES.values()], "errors": ["Not a directory"]}

    required_files = get_required_files(path.name)

    for key, filename in required_files.items():
        filepath = path / filename
        if not filepath.exists():
            result["missing"].append(filename)
            result["valid"] = False
            continue

        try:
            content = filepath.read_text(encoding="utf-8")
            if filename.endswith((".json", ".jsonld")):
                data = json.loads(content)
                if key == "manifest":
                    for field in ["id", "version"]:
                        if field not in data:
                            result["errors"].append(f"{filename} missing '{field}'")
                            result["valid"] = False
        except json.JSONDecodeError as e:
            result["errors"].append(f"{filename}: Invalid JSON - {e}")
            result["valid"] = False

    return result


def restamp(path: str | Path, new_version: str) -> Path:
    """Copy existing capsule to new folder with new version, renaming files."""
    path = Path(path)
    validation = validate_capsule(path)
    if not validation["valid"]:
        raise ValueError(f"Invalid source: {validation}")

    old_prefix = path.name
    old_files = get_required_files(old_prefix)
    manifest = json.loads((path / old_files["manifest"]).read_text(encoding="utf-8"))
    name = manifest.get("name", manifest["id"])
    new_id = generate_id(name, new_version)
    new_path = path.parent / new_id
    new_path.mkdir(parents=True, exist_ok=True)

    # Copy and rename files to new prefix
    for key, old_filename in old_files.items():
        old_filepath = path / old_filename
        new_filename = f"{new_id}{REQUIRED_SUFFIXES[key]}"
        new_filepath = new_path / new_filename

        if key == "kb":
            new_filepath.write_text(old_filepath.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            data = json.loads(old_filepath.read_text(encoding="utf-8"))
            if key == "manifest":
                data = {**data, "id": new_id, "version": new_version,
                        "previous_version": manifest["version"], "restamped": datetime.now().isoformat()}
            _write_json(new_filepath, data)

    return new_path


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cap1 = stamp_empty("Test Agent", tmp)
        print(f"Created: {cap1.name} | Valid: {validate_capsule(cap1)['valid']}")
        print(f"Files: {[f.name for f in cap1.iterdir()]}")
        cap2 = restamp(cap1, "1.1.0")
        files1 = get_required_files(cap1.name)
        files2 = get_required_files(cap2.name)
        m1 = json.loads((cap1 / files1["manifest"]).read_text())
        m2 = json.loads((cap2 / files2["manifest"]).read_text())
        print(f"Restamped: {m1['version']} -> {m2['version']}")
