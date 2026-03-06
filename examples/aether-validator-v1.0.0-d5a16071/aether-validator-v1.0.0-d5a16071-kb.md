# Aether Validator Agent

## Purpose
This agent validates LLM-generated content against structured reference data. It receives a response and a set of known facts, then returns a grounding report identifying which claims are verified, which are unverified, and which are qualitative.

## Validation Methodology
- Statement splitting: Break response into atomic claims
- Value extraction: Numbers, dates, percentages, names
- Deterministic matching: Compare extracted values against reference data with type-aware tolerance
- Scoring: grounded / (grounded + ungrounded), persona excluded
- Threshold: Configurable, default 0.8 (80% grounded minimum)

## Supported Value Types
- Numbers: integers, decimals, comma-grouped (1% tolerance)
- Percentages: N%, N percent, N pct
- Dates: Years (1700-2099), full dates (Month Day, Year → ISO)
- Names: Capitalized word sequences

## Output Format
Structured report with per-statement grounding analysis, gap identification, and aggregate score.
