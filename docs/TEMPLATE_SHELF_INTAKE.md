# Template Shelf Intake — the Codex "Paperwork folder" find

_Logged 2026-07-13 by the coding engineer (Claude, Anthropic) at the
proprietor's direction (Shannon Brian Kelley). Scope note per the
`scope-first` rule: this records an assessed intake and a PROPOSED
in-scope addition; no code changes accompany it._

## The find

`C:\Users\sbrya\OneDrive\Desktop\Paperwork folder` — a curated library of
BLANK, standards-anchored engineering templates with a written governance
policy (`TEMPLATE_LIBRARY_POLICY.md`): templates stay blank at the source;
projects copy and fill their own instances.

**That policy IS Imprint's operating model, stated as paperwork.** Imprint
presses project data into templates to produce filled documents; the Codex
is a ready-made, license-tracked shelf of source templates to press FROM.
Proof of the fit: on 2026-07-13 the Sentinel Forge project needed a daily
shop log — the engineer took the Codex signoff checklist, adapted it, and
filled it by hand (`Sentinel-Forge/docs/SHOP_LOG.md`). That whole exercise
is one Imprint workflow, performed manually.

## Assay — what's gold, what's gravel

**Gold (high template value for a 2026 shop):**
- `Engineering_Project_Build_And_Inventory_Blank_Template_Pack` — 9
  plain-text templates (build checklist, artifact/component/environment/
  dependency/config/deployment inventories, evidence-and-signoff
  checklist). Plain text, placeholder-driven (`{name}`, `{link_or_path}`)
  — near-zero conversion cost into Imprint templates.
- `Project development paperwork` — arc42 (multi-language), ADR/MADR, C4
  Model, OpenAPI, AsyncAPI, OWASP Threat Dragon, NIST AI RMF packs: the
  industry-standard architecture/decision/security document set.
- `TEMPLATE_LIBRARY_POLICY.md` — governance worth encoding as an Imprint
  RULE: sources read-only, instances per project.
- Licensing hygiene already present (`LICENSES/`, `UPSTREAM_SOURCES.md`)
  — carry each template's license into any Imprint ingestion.

**Gravel (leave in the pan):**
- `Complete code base/` — unrelated notes/scripts, not templates.
- Duplicated canonical packs across subfolders — dedupe on ingest.

## Verdict

**A gold vein, not a nugget — for Imprint specifically.** For Sentinel
Forge it was one useful checklist; for Imprint it is a starter CONTENT
LIBRARY plus a governance rule, i.e. the two things a document-automation
product needs on day one and usually has to author from scratch.

## Proposed in-scope addition (owner directed the intake; build timing is
a separate decision)

1. **Template Shelf**: ingest the gold-list packs as read-only source
   templates (with license lineage per template).
2. **Instance rule**: filled documents are always project-scoped copies;
   sources are immutable (the Codex policy, enforced in software).
3. **First proof**: reproduce the Sentinel Forge SHOP_LOG flow inside
   Imprint — blank signoff template + project data → dated, dual-signoff
   daily log. It was done by hand once; that manual run is the acceptance
   test's script.

_No build begins until this is reconciled with Imprint's own scope
baseline and the owner says go._
