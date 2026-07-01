"""imprint/models.py — pure definitions (the vocabulary of the domain).

No database, no GUI, no side effects. Just the controlled vocabularies Imprint
uses everywhere, so the rest of the app (and the tests) agree on the same terms.
This is the smallest, safest part of the functional core.
"""

from __future__ import annotations

# The three methodologies a project can be built under. Key = stored value
# (kept lowercase + stable for the database); value = human label for the UI.
# These map to ISO/IEC/IEEE 12207 lifecycle styles.
METHODOLOGIES: dict[str, str] = {
    "waterfall": "Waterfall (sequential, gated)",
    "vmodel": "V-Model (gated + test pairing)",
    "agile": "Agile (iterative, sprints)",
}

# Requirement classification (ISO/IEC/IEEE 29148 leans on these distinctions).
REQ_TYPES: list[str] = ["Functional", "Non-Functional", "Constraint", "Interface"]

# MoSCoW prioritisation — how a requirement earns its place in the baseline.
MOSCOW: list[str] = ["Must", "Should", "Could", "Won't"]

# Lifecycle of a single requirement record. "baselined" is the frozen state
# that scope-creep is later detected against (the guardrail).
REQ_STATUSES: list[str] = ["draft", "baselined", "changed", "removed"]


def methodology_label(key: str) -> str:
    """Human label for a stored methodology key ('waterfall' -> 'Waterfall (...)')."""
    return METHODOLOGIES.get(key, key)


def is_valid_methodology(key: str) -> bool:
    return key in METHODOLOGIES
