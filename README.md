# Imprint

> **Local-first SDLC paperwork automation.** Data pressed into a template → a finished
> document. Imprint fills out your software-project paperwork (SRS and the rest of the
> lifecycle documents) for you — 100% on your laptop, no cloud, no server, no API keys.

![Status](https://img.shields.io/badge/status-v1.1-success)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows-0078d4.svg)

---

## The core idea

Imprint is **project-centric with guardrails, not a template shelf.** You create a
project, pick a methodology, and Imprint walks it through its phases — prompting for the
right document at the right time and flagging when you drift out of scope.

**Requirements are data, not a document.** Each requirement is a structured record in
SQLite (ID, type, statement, MoSCoW priority, acceptance criteria, source, status,
links) — *stored once, presented three ways*:

- as a full **SRS** (Waterfall) — targeting **ISO/IEC/IEEE 29148**
- as **user stories + acceptance criteria** (Agile)
- as the left column of the **traceability matrix** (V-Model)

## Three methodologies (one engine, swappable profiles)

| | Waterfall | V-Model | Agile |
|---|---|---|---|
| Style | Sequential, gated | Gated + test pairing | Iterative, sprints |
| Star artifact | Full SRS | Traceability matrix | User stories |

Build order: **Waterfall first** (most document-complete) → V-Model → Agile.

## Architecture — functional core / imperative shell

Same shape as the Book Reader: the Tkinter app (`imprint_app.py`) is the UI shell;
all reusable, UI-free logic lives in the `imprint/` package and is unit-tested without
launching the GUI.

| Module | Responsibility |
| --- | --- |
| `imprint/db.py` | SQLite schema, CRUD, and an atomic `transaction()` primitive (ACID) |
| `imprint/models.py` | Pure definitions — methodologies, requirement types, MoSCoW, statuses |
| `imprint/srs.py` | Render a requirement set as an SRS (.docx), ISO/IEC/IEEE 29148 layout |
| `imprint/assistant.py` | Embedded local AI assistant (Ollama) — drafts requirements offline |
| `imprint/traceability.py` | Render requirements as a Traceability Matrix (.xlsx), V-Model view |
| `imprint/user_stories.py` | Render requirements as Agile user stories (.docx), grouped by MoSCoW |
| `imprint/guardrail.py` | Scope-drift detection vs a baseline (added/removed/changed, GREEN/YELLOW/RED) |
| `imprint/web_search.py` | Web search for the assistant (DuckDuckGo, stdlib only — no key, no account) |
| `imprint/doc_index.py` | Read-only indexer for local/OneDrive files (.docx, .pdf, .md, .txt, .html, .xlsx, .csv) |
| `imprint/retrieval.py` | Pure ranking — picks the indexed passages most relevant to a question (RAG) |
| `imprint/doc_writer.py` | Turns assistant text into real .docx letters and .xlsx tables (live formulas) |
| `imprint_app.py` | Tkinter desktop shell — projects, requirements, document generation, assistant panel |

## Roadmap

- ✅ **v0.1** — requirements-as-data core + minimal project/requirement UI
- ✅ **v0.2** — **SRS (.docx) rendering** from the requirement records (`python-docx`)
- ✅ **v0.3** — **embedded AI assistant** (local Ollama model, transplanted from Strata) drafts
  requirements from a rough note
- ✅ **v0.4** — **Traceability Matrix (.xlsx)** — the V-Model view, columns from the Codex
  Source Library template (`openpyxl`)
- ✅ **v0.5** — **Assistant conversation panel** — talk to the local model in the main window;
  it helps draft requirements and you save its replies straight into the project
- ✅ **v0.6** — **multi-requirement save** (checkbox picker captures every "The system shall…"
  line in a reply) + **Status column & baseline check-off** (double-click or button)
- ✅ **v0.7** — **conversation persistence** — each project's assistant conversation is saved to
  SQLite and resumes on reopen (no more re-asking the same questions)
- ✅ **v0.8** — **Agile user-story view** (.docx) — the third rendering; requirements become
  "As a user, I want… so that…" stories grouped by MoSCoW priority
- ✅ **v0.9** — **Scope Guard** (concept transplanted from Turbo) — lock a baseline, then detect
  scope drift (added / removed / changed) with GREEN / YELLOW / RED zones
- ✅ **v1.0** — **full CRUD**: edit & delete requirements (double-click to edit), delete a project
  (cascades its requirements, conversation, and baselines)
- ✅ **v1.1** — **assistant context tools**: 🌐 web search (DuckDuckGo, no API key), ☁ read-only
  index of local/OneDrive files the assistant can answer from, and 📄 document drafting —
  the assistant's replies become real .docx letters and .xlsx tables with working formulas
  *(this build)*
- 🔲 Methodology profiles (Waterfall gate engine → V-Model traceability → Agile sprints)

## Run it

```powershell
py -3 imprint_app.py
```

## Test it

```powershell
py -3 -m unittest discover -s tests
```

100% local. No cloud, no server, no API keys.

## License

MIT — see [LICENSE](LICENSE).
