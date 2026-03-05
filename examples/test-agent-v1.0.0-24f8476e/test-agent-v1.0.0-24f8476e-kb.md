# Test Agent Knowledge Base

This is a minimal knowledge base for testing the Aether framework.

## Overview

Aether is an Adaptive Embodied Thinking Holistic Evolutionary Runtime. It provides a clean agent framework built from scratch with zero external dependencies beyond the standard library.

## Capsules

A capsule is a folder containing 5 files that define an agent's identity and knowledge. Files are prefixed with the folder name following the pattern: {name}-v{version}-{uid8}

## Pipeline

The framework runs a 4-stage pipeline:
1. Distill: Extract intent and entities from input
2. Augment: Enrich with KB and KG context
3. Generate: Produce response via LLM
4. Review: Verify quality and grounding
