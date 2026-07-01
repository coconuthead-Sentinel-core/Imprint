"""imprint/guardrail.py — scope-drift detection (concept transplanted from Turbo).

Turbo guarded a codebase against its charter; Imprint guards a project against its
baselined requirements. Lock a baseline (a snapshot of the agreed requirement set),
then check whether the current requirements have drifted from it:

    added   = requirements new since the baseline   (scope creep)
    removed = baselined requirements now gone        (dropped scope)
    changed = same ID, different statement           (modified scope)

Zones mirror Turbo: GREEN (on-scope), YELLOW (additions/changes), RED (removals).
Pure and UI-free, so it's unit-tested without a window.
"""

from __future__ import annotations

ZONE_MESSAGE = {
    "GREEN": "On scope — current requirements match the baseline.",
    "YELLOW": "Scope has grown or shifted since the baseline — review the additions/changes.",
    "RED": "Baselined requirements are missing — scope has been dropped. Investigate.",
}


def check_drift(current, baseline_items) -> dict:
    """Compare current requirements to a baseline snapshot; return a drift report.

    `current` and `baseline_items` are lists of dict-like rows with `req_key`
    and `statement`. Returns {zone, added[], removed[], changed[], stable[]}.
    """
    cur = {r["req_key"]: (r["statement"] or "").strip() for r in current}
    base = {b["req_key"]: (b["statement"] or "").strip() for b in baseline_items}

    added = sorted(k for k in cur if k not in base)
    removed = sorted(k for k in base if k not in cur)
    changed = sorted(k for k in cur if k in base and cur[k] != base[k])
    stable = sorted(k for k in cur if k in base and cur[k] == base[k])

    if removed:
        zone = "RED"
    elif added or changed:
        zone = "YELLOW"
    else:
        zone = "GREEN"
    return {"zone": zone, "added": added, "removed": removed, "changed": changed, "stable": stable}


def summarize(report: dict, baseline_when: str = "") -> str:
    """Human-readable, Turbo-style summary of a drift report."""
    lines = [f"SCOPE GUARD — {report['zone']} ZONE", ZONE_MESSAGE[report["zone"]]]
    if baseline_when:
        lines.append(f"Baseline locked: {baseline_when}")
    lines.append("")

    def block(title, keys):
        if keys:
            lines.append(f"{title} ({len(keys)}): {', '.join(keys)}")

    block("⚠ Added since baseline", report["added"])
    block("✗ Removed since baseline", report["removed"])
    block("~ Changed since baseline", report["changed"])
    lines.append(f"✓ Stable: {len(report['stable'])}")
    if report["zone"] == "GREEN":
        lines.append("\nNothing has drifted. You're building exactly what was agreed.")
    return "\n".join(lines)
