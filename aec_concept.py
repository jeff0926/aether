"""
AEC Concept Layer 1 - Compiled Deterministic Matching
Adds concept-level statement matching using COMPILED token patterns from KG node labels.
The KG compiles into detector functions at load time. Runtime matching is set intersection.
"""

import re
from collections import Counter

# Stopwords removed from token sets
STOPWORDS = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
             'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
             'it', 'its', 'this', 'that', 'these', 'those', 'not', 'no', 'do', 'does',
             'did', 'has', 'have', 'had', 'will', 'would', 'could', 'should', 'may',
             'can', 'if', 'then', 'than', 'so', 'as', 'from', 'into', 'up', 'out',
             'about', 'over', 'such', 'each', 'every', 'all', 'any', 'both', 'few',
             'more', 'most', 'other', 'some', 'very', 'just', 'also', 'like', 'use',
             'using', 'used'}

# Type-specific configuration for matching
TYPE_CONFIG = {
    'rules':        {'match_threshold': 0.50, 'weight': 1.0},
    'techniques':   {'match_threshold': 0.55, 'weight': 1.0},
    'antipatterns': {'match_threshold': 0.40, 'weight': 1.0},
    'concepts':     {'match_threshold': 0.30, 'weight': 0.5},
    'tools':        {'match_threshold': 0.60, 'weight': 0.3},
    'traits':       {'match_threshold': 0.70, 'weight': 0.2},
}


def tokenize(text: str) -> set:
    """Extract content words as lowercase set, minus stopwords."""
    return set(re.findall(r'\b\w+\b', text.lower())) - STOPWORDS


def dice_bigram(s1: str, s2: str) -> float:
    """Sørensen-Dice coefficient using word bigrams. Secondary check."""
    def bigrams(text):
        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) < 2:
            return Counter()
        return Counter(f"{words[i]} {words[i+1]}" for i in range(len(words) - 1))
    bg1, bg2 = bigrams(s1), bigrams(s2)
    intersection = sum((bg1 & bg2).values())
    total = sum(bg1.values()) + sum(bg2.values())
    return (2 * intersection) / total if total > 0 else 0.0


def compile_kg(kg_nodes: list) -> dict:
    """
    Compile KG into executable detector structures.
    Called ONCE at capsule load. All runtime matching uses the compiled output.

    Returns:
        {
            'detectors': [...],      # compiled pattern detectors
            'blacklist': set,        # anti-pattern forbidden tokens
            'blacklist_map': dict,   # token -> node_id mapping for violation attribution
        }
    """
    detectors = []
    blacklist = set()
    blacklist_map = {}  # token -> {'node_id': ..., 'label': ...}

    for node in kg_nodes:
        ntype = node.get('@type', '')
        label = node.get('rdfs:label', '')
        node_id = node.get('@id', '')
        if not label or not node_id:
            continue

        # Classify node type
        if 'Rule' in ntype:
            node_type = 'rules'
        elif 'AntiPattern' in ntype:
            node_type = 'antipatterns'
        elif 'Technique' in ntype:
            node_type = 'techniques'
        elif 'Concept' in ntype:
            node_type = 'concepts'
        elif 'Tool' in ntype:
            node_type = 'tools'
        elif 'Trait' in ntype:
            node_type = 'traits'
        else:
            continue

        config = TYPE_CONFIG.get(node_type, {'match_threshold': 0.5, 'weight': 0.5})

        # COMPILE: Extract content tokens from label
        patterns = tokenize(label)

        detectors.append({
            'node_id': node_id,
            'label': label,
            'node_type': node_type,
            'patterns': patterns,
            'pattern_count': len(patterns),
            'threshold': config['match_threshold'],
            'weight': config['weight'],
            'node': node,
        })

        # COMPILE: Anti-pattern blacklist
        if node_type == 'antipatterns':
            # Extract specific terms from parentheses: "Overused fonts (Inter, Roboto)" -> {inter, roboto}
            paren_terms = re.findall(r'\(([^)]+)\)', label)
            for match in paren_terms:
                for term in re.split(r'[,/]', match):
                    term = term.strip().lower()
                    if len(term) > 2:
                        blacklist.add(term)
                        blacklist_map[term] = {'node_id': node_id, 'label': label}
    return {
        'detectors': detectors,
        'blacklist': blacklist,
        'blacklist_map': blacklist_map,
    }


def check_violation(stmt_tokens: set, compiled: dict) -> dict | None:
    """Check if statement tokens hit the anti-pattern blacklist. O(1) per token."""
    hits = stmt_tokens & compiled['blacklist']
    if not hits:
        return None

    # Find best matching anti-pattern node
    node_scores = {}
    for hit in hits:
        mapped = compiled['blacklist_map'].get(hit)
        if mapped:
            nid = mapped['node_id']
            node_scores[nid] = node_scores.get(nid, 0) + 1

    if not node_scores:
        return None

    best_id = max(node_scores, key=node_scores.get)
    best_node = compiled['blacklist_map'].get(list(hits)[0], {})

    return {
        'node_id': best_id,
        'label': best_node.get('label', ''),
        'hits': list(hits),
        'type': 'antipattern_violation',
    }


def match_statement(stmt_tokens: set, statement: str, compiled: dict) -> dict:
    """
    Match a single statement against compiled KG detectors.

    Primary: set intersection (O(1) per detector)
    Secondary: Dice bigram (only when set overlap is in ambiguous range)

    Returns:
        {
            'category': 'concept_grounded' | 'antipattern_violation' | 'concept_persona',
            'matches': [...],
            'violation': {...} or None,
            'ambiguous': [...]  # candidates for Layer 2 LLM check
        }
    """
    # Step 1: Anti-pattern violation check (highest priority, fastest)
    violation = check_violation(stmt_tokens, compiled)
    if violation:
        return {
            'category': 'antipattern_violation',
            'matches': [],
            'violation': violation,
            'ambiguous': [],
        }

    # Step 2: Run compiled detectors via set intersection
    matches = []
    ambiguous = []

    for detector in compiled['detectors']:
        if detector['pattern_count'] == 0:
            continue

        # PRIMARY: Set intersection
        overlap = stmt_tokens & detector['patterns']
        coverage = len(overlap) / detector['pattern_count']

        if coverage >= detector['threshold']:
            # High confidence match
            matches.append({
                'node_id': detector['node_id'],
                'label': detector['label'],
                'node_type': detector['node_type'],
                'coverage': round(coverage, 3),
                'overlap_tokens': list(overlap),
                'weight': detector['weight'],
                'method': 'compiled_pattern',
            })
        elif coverage >= detector['threshold'] * 0.5:
            # Ambiguous range - secondary Dice check
            dice = dice_bigram(statement, detector['label'])
            if dice >= 0.3:
                ambiguous.append({
                    'node_id': detector['node_id'],
                    'label': detector['label'],
                    'node_type': detector['node_type'],
                    'coverage': round(coverage, 3),
                    'dice': round(dice, 3),
                    'weight': detector['weight'],
                    'node': detector['node'],
                    'method': 'dice_ambiguous',
                })

    # Step 3: Determine category
    if matches:
        strong = [m for m in matches if m['weight'] >= 0.5]
        if strong:
            return {
                'category': 'concept_grounded',
                'matches': sorted(matches, key=lambda m: m['coverage'], reverse=True),
                'violation': None,
                'ambiguous': ambiguous,
            }

    return {
        'category': 'concept_persona',
        'matches': matches,
        'violation': None,
        'ambiguous': sorted(ambiguous, key=lambda a: a.get('dice', 0), reverse=True)[:3],
    }


def concept_verify(response_text: str, kg_nodes: list, compiled: dict = None) -> dict:
    """
    Run concept-level AEC on a response.

    If compiled dict is provided (from capsule load), uses it directly.
    Otherwise compiles on the fly (for standalone verify).
    """
    from aec import split_statements

    if compiled is None:
        compiled = compile_kg(kg_nodes)

    statements = split_statements(response_text)

    grounded = 0
    ungrounded = 0
    persona = 0
    details = []
    gaps = []

    for stmt in statements:
        stmt_tokens = tokenize(stmt)
        result = match_statement(stmt_tokens, stmt, compiled)

        if result['category'] == 'concept_grounded':
            grounded += 1
            top = result['matches'][0]
            details.append({
                'statement': stmt,
                'category': 'grounded',
                'method': f"concept:{top['node_type']}",
                'matched_node': top['node_id'],
                'matched_label': top['label'],
                'coverage': top['coverage'],
                'overlap_tokens': top['overlap_tokens'],
            })
        elif result['category'] == 'antipattern_violation':
            ungrounded += 1
            v = result['violation']
            details.append({
                'statement': stmt,
                'category': 'ungrounded',
                'method': 'antipattern_violation',
                'matched_node': v['node_id'],
                'matched_label': v['label'],
                'violation_terms': v['hits'],
            })
            gaps.append({
                'text': f"VIOLATION: '{', '.join(v['hits'])}' matches antipattern '{v['label']}'",
                'node_id': v['node_id'],
            })
        else:
            persona += 1
            details.append({
                'statement': stmt,
                'category': 'persona',
                'method': 'no_concept_match',
                'ambiguous_candidates': [
                    {'node_id': a['node_id'], 'dice': a.get('dice', 0)}
                    for a in result.get('ambiguous', [])
                ],
            })

    total = grounded + ungrounded
    score = grounded / total if total > 0 else 1.0

    return {
        'score': round(score, 4),
        'grounded_statements': grounded,
        'ungrounded_statements': ungrounded,
        'persona_statements': persona,
        'total_statements': grounded + ungrounded + persona,
        'details': details,
        'gaps': gaps,
        'method': 'concept_compiled',
    }


def has_typed_nodes(kg_nodes: list) -> bool:
    """Check if KG has nodes with Rule/AntiPattern/Technique/Concept/Tool types."""
    type_markers = ('Rule', 'AntiPattern', 'Technique', 'Concept', 'Tool')
    for node in kg_nodes:
        ntype = node.get('@type', '')
        if ntype and any(t in ntype for t in type_markers):
            return True
    return False


if __name__ == "__main__":
    import time
    import json

    # Test with frontend-design KG
    kg_path = 'examples/frontend-design-v1.0.0-ff6ab491/frontend-design-v1.0.0-ff6ab491-kg.jsonld'
    try:
        with open(kg_path) as f:
            kg = json.load(f)
        nodes = kg.get('@graph', [])
    except FileNotFoundError:
        print(f"KG not found: {kg_path}")
        nodes = []

    if nodes:
        # Test compilation performance
        start = time.time()
        compiled = compile_kg(nodes)
        compile_time = (time.time() - start) * 1000

        print(f"Compile time: {compile_time:.2f}ms")
        print(f"Detectors: {len(compiled['detectors'])}")
        print(f"Blacklist tokens: {len(compiled['blacklist'])}")
        print(f"Blacklist sample: {list(compiled['blacklist'])[:10]}")

        # Test statements
        tests = [
            ("Use CSS variables for consistency", "should be GROUNDED (rule match)"),
            ("Implement staggered reveals using animation-delay", "should be GROUNDED (technique match)"),
            ("Use Inter for the body text", "should be UNGROUNDED (antipattern violation)"),
            ("Your typography should feel handcrafted", "should be PERSONA (no match)"),
        ]

        print("\n--- Statement Tests ---")
        for stmt, expected in tests:
            tokens = tokenize(stmt)
            result = match_statement(tokens, stmt, compiled)
            print(f"\nStatement: {stmt}")
            print(f"Expected: {expected}")
            print(f"Category: {result['category']}")
            if result['matches']:
                top = result['matches'][0]
                print(f"Match: {top['label']} (coverage={top['coverage']}, tokens={top['overlap_tokens']})")
            if result['violation']:
                print(f"Violation: {result['violation']['label']} (hits={result['violation']['hits']})")
