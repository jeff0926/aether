"""
CLI - Command-line interface for Aether.
"""

import argparse
import json
from pathlib import Path

from aether import Capsule, validate_folder, get_required_files
from stamper import stamp_empty, stamp_from_source, validate_capsule
from llm import make_llm_fn
from kg import load_kg, stats as kg_stats
from aec import verify


def cmd_stamp(args):
    """Create a new capsule."""
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    if args.source:
        path = stamp_from_source(args.name, args.source, output, args.version)
        print(f"Stamped from source: {path}")
    else:
        path = stamp_empty(args.name, output, args.version)
        print(f"Stamped empty: {path}")

    validation = validate_capsule(path)
    print(f"Valid: {validation['valid']}")


def cmd_run(args):
    """Run a capsule with a query."""
    missing = validate_folder(args.capsule)
    if missing:
        print(f"Invalid capsule. Missing: {missing}")
        return

    llm_fn = make_llm_fn(provider=args.provider, model=args.model)
    capsule = Capsule(args.capsule, llm_fn=llm_fn)

    print(f"Running: {capsule}")
    print(f"Query: {args.query}\n")

    ctx = capsule.run(args.query)

    # Run AEC verification
    kg_nodes = ctx["augmented"].get("kg", [])
    aec_result = verify(ctx["generated"], kg_nodes)

    print(f"Generated:\n{ctx['generated']}\n")
    print(f"AEC Score: {aec_result['score']} (threshold: {aec_result['threshold']})")
    print(f"AEC Passed: {aec_result['passed']}")
    print(f"Statements: {aec_result['grounded_statements']}G / {aec_result['ungrounded_statements']}U / {aec_result['persona_statements']}P")


def cmd_validate(args):
    """Validate a capsule folder."""
    result = validate_capsule(args.capsule)
    print(f"Path: {args.capsule}")
    print(f"Valid: {result['valid']}")
    if result["missing"]:
        print(f"Missing: {result['missing']}")
    if result["errors"]:
        print(f"Errors: {result['errors']}")


def cmd_info(args):
    """Show capsule information."""
    missing = validate_folder(args.capsule)
    if missing:
        print(f"Invalid capsule. Missing: {missing}")
        return

    capsule_path = Path(args.capsule)
    capsule = Capsule(capsule_path)
    files = get_required_files(capsule_path.name)
    kg = load_kg(capsule_path / files["kg"])

    print(f"ID: {capsule.id}")
    print(f"Name: {capsule.name}")
    print(f"Version: {capsule.version}")
    print(f"Path: {capsule.path}")
    print(f"\nKG Stats: {kg_stats(kg)}")
    print(f"KB Size: {len(capsule.files['kb'])} chars")

    # File sizes
    print("\nFiles:")
    for key, filename in files.items():
        size = (capsule_path / filename).stat().st_size
        print(f"  {filename}: {size} bytes")


def main():
    parser = argparse.ArgumentParser(prog="aether", description="Aether Capsule Framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stamp
    p_stamp = subparsers.add_parser("stamp", help="Create a new capsule")
    p_stamp.add_argument("name", help="Capsule name")
    p_stamp.add_argument("--source", help="Source file (.md, .json, .jsonld)")
    p_stamp.add_argument("--output", default="./capsules", help="Output directory")
    p_stamp.add_argument("--version", default="1.0.0", help="Version string")
    p_stamp.set_defaults(func=cmd_stamp)

    # run
    p_run = subparsers.add_parser("run", help="Run capsule with query")
    p_run.add_argument("capsule", help="Path to capsule folder")
    p_run.add_argument("query", help="Query to process")
    p_run.add_argument("--provider", default="stub", help="LLM provider")
    p_run.add_argument("--model", help="Model name")
    p_run.set_defaults(func=cmd_run)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate capsule")
    p_validate.add_argument("capsule", help="Path to capsule folder")
    p_validate.set_defaults(func=cmd_validate)

    # info
    p_info = subparsers.add_parser("info", help="Show capsule info")
    p_info.add_argument("capsule", help="Path to capsule folder")
    p_info.set_defaults(func=cmd_info)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
