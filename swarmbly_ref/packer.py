"""Packing and the context budget (E2, E6, E20): Gamma header, flanks,
packets, and rho."""

from . import units


def build_gamma(task):
    """Global contract: objective, format, constraints, entity glossary."""
    entities = ", ".join(task.get("entities", {}).keys()) or "—"
    lines = [
        f"OBJECTIVE: {task['objective']}",
        f"FORMAT: {task.get('format', 'prose')}",
        "AUDIENCE: technical staff",
        f"ENTITIES (use these exact names): {entities}",
    ]
    constraints = task.get("global_constraints", [])
    if constraints:
        lines.append("CONSTRAINTS: " + "; ".join(constraints))
    return "\n".join(lines)


def build_packet(task, gamma, fragment_text, flank_lead, flank_trail,
                 unique_here, instruction, F_sentences):
    """One dispatched packet: Gamma (never trimmed) + flanks + material + task."""
    parts = [gamma]
    if flank_lead:
        parts.append(f"CONTEXT BEFORE (flank, for continuity; do not duplicate):\n{flank_lead}")
    parts.append(f"MATERIAL (your assigned fragment, {len(units.split_sentences(fragment_text))} sentences):\n{fragment_text}")
    if flank_trail:
        parts.append(f"CONTEXT AFTER (flank, for continuity; do not duplicate):\n{flank_trail}")
    if unique_here:
        parts.append("UNIQUE_TERMS (mention each EXACTLY once, and only here): "
                     + ", ".join(unique_here))
    parts.append(f"TASK: {instruction}")
    return "\n\n".join(parts)


def packet_budget(packet_text, material_tokens):
    """Tokens of one packet and its share of rho."""
    return units.approx_tokens(packet_text)


def rho_total(packet_texts, material_tokens):
    """rho = sum |K_i| / |P| — the price of fragmentation."""
    total = sum(units.approx_tokens(p) for p in packet_texts)
    return round(total / max(1, material_tokens), 3), total
