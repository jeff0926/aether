# Test Knowledge Base

This is a minimal knowledge base for testing the Aether framework.

## Overview

Aether is an Adaptive Embodied Thinking Holistic Evolutionary Runtime. It provides a clean agent framework built from scratch with zero external dependencies beyond the standard library.

## Capsules

A capsule is a folder containing 5 files that define an agent's identity and knowledge. Files are prefixed with the folder name:
- {folder}-manifest.json: Metadata and identity
- {folder}-definition.json: Behavioral configuration
- {folder}-persona.json: Personality and tone
- {folder}-kb.md: Knowledge base as markdown
- {folder}-kg.jsonld: Knowledge graph as JSON-LD

## Pipeline

The framework runs a 4-stage pipeline:
1. Distill: Extract intent and entities from input
2. Augment: Enrich with KB and KG context
3. Generate: Produce response via LLM
4. Review: Verify quality and grounding
