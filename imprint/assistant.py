"""imprint/assistant.py — the embedded AI assistant (transplanted from Strata).

Reuses Strata's proven, RAM-safe approach to the LOCAL model: the only network
touch is the loopback to the Ollama daemon on this machine. If Ollama isn't
installed / running / pulled, `.available` is False and callers fall back
gracefully — the assistant never breaks the app.

Here the assistant has one focused job: turn a rough note into a clean,
verifiable requirement (ISO/IEC/IEEE 29148 style) plus a starter acceptance
criterion, to speed up filling out the paperwork.
"""

from __future__ import annotations

import os

try:
    import ollama
    _OLLAMA_IMPORTED = True
except Exception:
    _OLLAMA_IMPORTED = False

# Same small default model Strata proved on an 8 GB laptop.
MODEL = os.environ.get("IMPRINT_MODEL", "llama3.2:3b")


def parse_draft(reply: str) -> dict:
    """Pull a requirement statement + acceptance criteria out of the model reply.

    Pure function (no Ollama) so it can be unit-tested. Tolerant of a plain reply:
    if no labels are found, the whole reply becomes the statement.
    """
    statement, criteria = "", ""
    for raw in (reply or "").splitlines():
        line = raw.strip().lstrip("-*0123456789. ").strip()
        low = line.lower()
        if low.startswith("statement:"):
            statement = line.split(":", 1)[1].strip()
        elif low.startswith(("acceptance", "acceptance criteria:", "criteria:")):
            criteria = line.split(":", 1)[1].strip() if ":" in line else ""
    if not statement:
        # No labels — treat the first non-empty line as the requirement.
        for raw in (reply or "").splitlines():
            if raw.strip():
                statement = raw.strip()
                break
    return {"statement": statement, "acceptance_criteria": criteria}


def extract_requirement(text: str) -> str:
    """Pull a 'The system shall ...' line out of a chat reply (pure, testable).

    Falls back to the first non-empty line if no canonical form is present.
    """
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-*0123456789. ").strip()
        if line.lower().startswith("the system shall"):
            return line.rstrip(".") + "." if not line.endswith(".") else line
    for raw in (text or "").splitlines():
        if raw.strip():
            return raw.strip()
    return ""


class RequirementAssistant:
    """Wraps the local model for requirement drafting. Mirrors Strata's LLMBrain."""

    def __init__(self, model: str = MODEL):
        self.model = model
        self.available = False
        self.last_error: str | None = None
        # Keep the KV cache small so llama3.2 doesn't try to grab ~15 GB and OOM
        # on an 8 GB machine (the hard-won Strata setting).
        self.num_ctx = int(os.environ.get("IMPRINT_NUM_CTX", "2048"))
        self.keep_alive = os.environ.get("IMPRINT_KEEP_ALIVE", "10m")

        if not _OLLAMA_IMPORTED:
            self.last_error = "ollama package not installed"
            return
        try:
            names = self._installed_models()
            self.available = any(self.model.split(":")[0] in n for n in names)
            if not self.available:
                self.last_error = f"model '{self.model}' not pulled (run: ollama pull {self.model})"
        except Exception as e:
            self.last_error = f"Ollama daemon not reachable: {type(e).__name__}"

    @staticmethod
    def _installed_models() -> list[str]:
        """Installed model names, tolerant of ollama library version differences."""
        data = ollama.list()
        models = getattr(data, "models", None)
        if models is None and isinstance(data, dict):
            models = data.get("models", [])
        names = []
        for m in (models or []):
            n = getattr(m, "model", None)
            if n is None and isinstance(m, dict):
                n = m.get("model") or m.get("name")
            if n:
                names.append(n)
        return names

    def draft_requirement(self, rough_note: str, project_name: str = "") -> dict | None:
        """Turn a rough note into a requirement dict, or None if unavailable/errored."""
        rough_note = (rough_note or "").strip()
        if not rough_note or not self.available:
            return None
        ctx = f" for the project '{project_name}'" if project_name else ""
        system = (
            "You are Imprint's requirements assistant, running fully offline on the "
            "user's computer. Rewrite the user's rough note as ONE clear, verifiable "
            f"software requirement{ctx}, following ISO/IEC/IEEE 29148 style (unambiguous, "
            "testable, in the form 'The system shall ...'). Reply in EXACTLY this format:\n"
            "Statement: <the requirement>\n"
            "Acceptance criteria: <one short, testable criterion>\n"
            "Do not add anything else."
        )
        try:
            resp = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": rough_note},
                ],
                keep_alive=self.keep_alive,
                options={"temperature": 0.3, "num_predict": 256, "num_ctx": self.num_ctx},
            )
            return parse_draft(resp["message"]["content"])
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return None

    def _chat_system(self, project_name: str, methodology: str) -> str:
        ctx = f" for the project '{project_name}'" if project_name else ""
        method = f" The team is using the {methodology} methodology." if methodology else ""
        return (
            "You are Imprint's requirements assistant, running fully offline on the user's "
            f"computer. You help the user capture and refine the software requirements{ctx}.{method} "
            "Ask focused questions, one at a time, to draw out what the system must do. "
            "When a requirement becomes clear, state it on its own line in the form "
            "'The system shall ...' so it can be saved to the project. Keep replies short and concrete."
        )

    def chat(self, history: list[dict], project_name: str = "", methodology: str = "") -> str | None:
        """Continue a conversation. `history` is [{role, content}, ...]; returns the reply or None."""
        if not self.available:
            return None
        # Trim to the most recent turns so the small context window isn't overrun.
        recent = list(history)[-12:]
        messages = [{"role": "system", "content": self._chat_system(project_name, methodology)}] + recent
        try:
            resp = ollama.chat(
                model=self.model,
                messages=messages,
                keep_alive=self.keep_alive,
                options={"temperature": 0.5, "num_predict": 400, "num_ctx": self.num_ctx},
            )
            return resp["message"]["content"].strip()
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            return None
