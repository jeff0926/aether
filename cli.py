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
from education import queue_stats, get_pending, get_oldest_pending, educate
from ingest import ingest_research, ingest_document


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

    # AEC results come from pipeline review stage
    aec_result = ctx["review"]["aec"]

    print(f"Generated:\n{ctx['generated']}\n")
    print(f"AEC Score: {aec_result['score']} (threshold: {aec_result['threshold']})")
    print(f"AEC Passed: {aec_result['passed']}")
    print(f"Statements: {aec_result['grounded_statements']}G / {aec_result['ungrounded_statements']}U / {aec_result['persona_statements']}P")

    # Print telemetry
    tel = ctx.get("telemetry", {})
    stages = tel.get("stages", {})
    print(f"\n--- Telemetry ---")
    print(f"Total: {tel.get('total_ms', 0):.1f}ms")

    if "distill" in stages:
        d = stages["distill"]
        print(f"  Distill:  {d['time_ms']:6.1f}ms | entities: {d['entities_extracted']}")

    if "augment" in stages:
        a = stages["augment"]
        print(f"  Augment:  {a['time_ms']:6.1f}ms | kb: {a['kb_matches']}, kg: {a['kg_matches']}")

    if "generate" in stages:
        g = stages["generate"]
        print(f"  Generate: {g['time_ms']:6.1f}ms | prompt: {g['prompt_chars']} chars")
        if g.get("tokens_in") or g.get("tokens_out"):
            print(f"            tokens: {g['tokens_in']} in, {g['tokens_out']} out")

    if "review" in stages:
        r = stages["review"]
        print(f"  Review:   {r['time_ms']:6.1f}ms")

    # Full report if requested
    if args.report == "full":
        from report import print_report
        print_report(ctx, aec_result, capsule)


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


def cmd_queue(args):
    """Show education queue stats and pending items."""
    capsule_path = Path(args.capsule)
    if not capsule_path.is_dir():
        print(f"Invalid capsule path: {args.capsule}")
        return

    stats = queue_stats(capsule_path)
    print(f"Education Queue: {capsule_path.name}")
    print(f"  Total:       {stats['total']}")
    print(f"  Pending:     {stats['pending']}")
    print(f"  Researching: {stats['researching']}")
    print(f"  Validated:   {stats['validated']}")
    print(f"  Integrated:  {stats['integrated']}")
    print(f"  Failed:      {stats['failed']}")

    pending = get_pending(capsule_path)
    if pending:
        print(f"\nPending items ({len(pending)}):")
        for item in pending[:10]:  # Show first 10
            query = item.get("query", "")[:50]
            score = item.get("aec_score", 0)
            print(f"  [{item['id']}] score={score:.2f} | {query}...")
        if len(pending) > 10:
            print(f"  ... and {len(pending) - 10} more")
    else:
        print("\nNo pending items.")


def cmd_educate(args):
    """Run self-education on a pending failure."""
    capsule_path = Path(args.capsule)
    if not capsule_path.is_dir():
        print(f"Invalid capsule path: {args.capsule}")
        return

    # Get record ID - either specified or oldest pending
    if args.record_id:
        record_id = args.record_id
    else:
        oldest = get_oldest_pending(capsule_path)
        if not oldest:
            print("No pending failures to educate.")
            return
        record_id = oldest["id"]

    print(f"Educating: {record_id}")
    print(f"Capsule: {capsule_path.name}")

    # Create LLM function
    llm_fn = make_llm_fn(provider=args.provider, model=args.model)

    # Run education
    result = educate(capsule_path, record_id, llm_fn)

    print(f"\n--- Education Result ---")
    print(f"Status: {result['status']}")
    print(f"Original Score: {result['original_score']:.2f}")
    print(f"New Score: {result['new_score']:.2f}")
    print(f"Triples Added: {result['triples_added']}")
    if result.get("research_tokens"):
        tokens = result["research_tokens"]
        print(f"Research Tokens: {tokens.get('in', 0)} in, {tokens.get('out', 0)} out")
    if result.get("reason"):
        print(f"Reason: {result['reason']}")


def cmd_verify(args):
    """Run standalone AEC verification."""
    from aec import verify
    from kg import get_nodes

    # Load text (from arg or file)
    text = args.text
    if Path(text).exists():
        text = Path(text).read_text(encoding="utf-8")

    # Load reference KG
    kg = load_kg(args.reference)
    nodes = get_nodes(kg)

    threshold = args.threshold or 0.8
    result = verify(text, nodes, threshold)

    print(f"AEC Score: {result['score']} (threshold: {result['threshold']})")
    print(f"Passed: {result['passed']}")
    print(f"Statements: {result['grounded_statements']}G / {result['ungrounded_statements']}U / {result['persona_statements']}P")
    print(f"Persona Ratio: {result['persona_ratio']}")
    if result['gaps']:
        print(f"\nGaps ({len(result['gaps'])}):")
        for g in result['gaps']:
            print(f"  - {g['text'][:80]}...")


def cmd_ingest_research(args):
    """Ingest deep research output into a capsule."""
    source = Path(args.source)
    if not source.exists():
        print(f"Source not found: {source}")
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    path = ingest_research(source, output, args.name, args.version)
    print(f"Ingested: {path}")
    from stamper import validate_capsule
    print(f"Valid: {validate_capsule(path)['valid']}")


def cmd_ingest(args):
    """Ingest any document into a capsule with LLM extraction."""
    source = Path(args.source)
    if not source.exists():
        print(f"Source not found: {source}")
        return
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    llm_fn = make_llm_fn(provider=args.provider, model=args.model) if args.provider != "stub" else None
    path = ingest_document(source, output, args.name, agent_type=args.agent_type,
                           version=args.version, llm_fn=llm_fn)
    print(f"Ingested: {path}")
    from stamper import validate_capsule
    print(f"Valid: {validate_capsule(path)['valid']}")


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
    p_run.add_argument("--report", choices=["full"], help="Print execution report")
    p_run.set_defaults(func=cmd_run)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate capsule")
    p_validate.add_argument("capsule", help="Path to capsule folder")
    p_validate.set_defaults(func=cmd_validate)

    # info
    p_info = subparsers.add_parser("info", help="Show capsule info")
    p_info.add_argument("capsule", help="Path to capsule folder")
    p_info.set_defaults(func=cmd_info)

    # queue
    p_queue = subparsers.add_parser("queue", help="Show education queue")
    p_queue.add_argument("capsule", help="Path to capsule folder")
    p_queue.set_defaults(func=cmd_queue)

    # educate
    p_educate = subparsers.add_parser("educate", help="Run self-education on pending failure")
    p_educate.add_argument("capsule", help="Path to capsule folder")
    p_educate.add_argument("--record-id", help="Specific failure record ID (default: oldest pending)")
    p_educate.add_argument("--provider", default="anthropic", help="LLM provider")
    p_educate.add_argument("--model", help="Model name")
    p_educate.set_defaults(func=cmd_educate)

    # verify
    p_verify = subparsers.add_parser("verify", help="Standalone AEC verification")
    p_verify.add_argument("text", help="Text to verify (or path to text file)")
    p_verify.add_argument("--reference", "-r", required=True, help="Reference KG file (.jsonld)")
    p_verify.add_argument("--threshold", "-t", type=float, default=0.8)
    p_verify.set_defaults(func=cmd_verify)

    # ingest-research
    p_ingest_r = subparsers.add_parser("ingest-research", help="Ingest deep research output into capsule")
    p_ingest_r.add_argument("source", help="Path to deep research markdown file")
    p_ingest_r.add_argument("name", help="Agent name")
    p_ingest_r.add_argument("--output", default="./capsules", help="Output directory")
    p_ingest_r.add_argument("--version", default="1.0.0", help="Version string")
    p_ingest_r.set_defaults(func=cmd_ingest_research)

    # ingest
    p_ingest = subparsers.add_parser("ingest", help="Ingest any document into capsule (LLM-assisted)")
    p_ingest.add_argument("source", help="Path to markdown file")
    p_ingest.add_argument("name", help="Agent name")
    p_ingest.add_argument("--type", default="scholar", dest="agent_type", help="Agent type")
    p_ingest.add_argument("--output", default="./capsules", help="Output directory")
    p_ingest.add_argument("--version", default="1.0.0", help="Version string")
    p_ingest.add_argument("--provider", default="stub", help="LLM provider")
    p_ingest.add_argument("--model", help="Model name")
    p_ingest.set_defaults(func=cmd_ingest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
