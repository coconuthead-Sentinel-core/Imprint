"""Imprint — local-first SDLC paperwork automation (Tkinter shell).

This file is the *imperative shell*: it draws the window and wires buttons to the
functions in the `imprint/` package. It holds no business logic of its own, so
the logic can be tested without opening a window.

Run:  py -3 imprint_app.py
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from imprint import db, models, srs, assistant, traceability, user_stories, guardrail

# Larger, readable fonts (accessibility-first, like the Book Reader).
FONT = ("Segoe UI", 12)
FONT_BOLD = ("Segoe UI", 13, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")


def _enable_dpi_awareness() -> None:
    """Sharpen the UI on high-DPI Windows (avoids the blurry-Tk look)."""
    try:
        from ctypes import windll  # Windows only
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass  # non-Windows or older Windows — no harm done


class ProjectDialog(tk.Toplevel):
    """Modal 'New Project' form: name + methodology."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("New Project")
        self.resizable(False, False)
        self.result: tuple[str, str, str] | None = None
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=16)
        frm.grid(sticky="nsew")

        ttk.Label(frm, text="Project name", font=FONT_BOLD).grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.name_var, font=FONT, width=40).grid(
            row=1, column=0, sticky="ew", pady=(2, 12)
        )

        ttk.Label(frm, text="Methodology", font=FONT_BOLD).grid(row=2, column=0, sticky="w")
        self.method_var = tk.StringVar(value=models.METHODOLOGIES["waterfall"])
        ttk.Combobox(
            frm, textvariable=self.method_var, font=FONT, state="readonly",
            values=list(models.METHODOLOGIES.values()), width=38,
        ).grid(row=3, column=0, sticky="ew", pady=(2, 12))

        ttk.Label(frm, text="Description (optional)", font=FONT_BOLD).grid(row=4, column=0, sticky="w")
        self.desc = tk.Text(frm, font=FONT, width=40, height=3, wrap="word")
        self.desc.grid(row=5, column=0, sticky="ew", pady=(2, 12))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Create", command=self._on_create).grid(row=0, column=1)

        self.name_var and self.after(50, lambda: self.focus())

    def _on_create(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Please enter a project name.", parent=self)
            return
        # Map the human label back to the stored key.
        label = self.method_var.get()
        key = next((k for k, v in models.METHODOLOGIES.items() if v == label), "waterfall")
        self.result = (name, key, self.desc.get("1.0", "end").strip())
        self.destroy()


class RequirementDialog(tk.Toplevel):
    """Modal 'Add Requirement' form."""

    def __init__(self, parent, req_assistant=None):
        super().__init__(parent)
        self.title("Add Requirement")
        self.resizable(False, False)
        self.result: dict | None = None
        self.assistant = req_assistant
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=16)
        frm.grid(sticky="nsew")

        header = ttk.Frame(frm)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Statement", font=FONT_BOLD).grid(row=0, column=0, sticky="w")
        self.draft_btn = ttk.Button(header, text="✨ Draft with assistant", command=self._draft)
        self.draft_btn.grid(row=0, column=1, sticky="e")
        self.assist_status = ttk.Label(frm, text="", font=("Segoe UI", 10))
        self.assist_status.grid(row=2, column=0, columnspan=2, sticky="w")

        self.statement = tk.Text(frm, font=FONT, width=52, height=3, wrap="word")
        self.statement.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 2))

        ttk.Label(frm, text="Type", font=FONT_BOLD).grid(row=3, column=0, sticky="w")
        self.type_var = tk.StringVar(value=models.REQ_TYPES[0])
        ttk.Combobox(frm, textvariable=self.type_var, font=FONT, state="readonly",
                     values=models.REQ_TYPES, width=22).grid(row=4, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(frm, text="Priority (MoSCoW)", font=FONT_BOLD).grid(row=3, column=1, sticky="w")
        self.moscow_var = tk.StringVar(value=models.MOSCOW[0])
        ttk.Combobox(frm, textvariable=self.moscow_var, font=FONT, state="readonly",
                     values=models.MOSCOW, width=22).grid(row=4, column=1, sticky="ew")

        ttk.Label(frm, text="Acceptance criteria", font=FONT_BOLD).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.accept = tk.Text(frm, font=FONT, width=52, height=3, wrap="word")
        self.accept.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(2, 12))

        ttk.Label(frm, text="Source (optional)", font=FONT_BOLD).grid(row=7, column=0, columnspan=2, sticky="w")
        self.source_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.source_var, font=FONT, width=52).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(2, 12))

        btns = ttk.Frame(frm)
        btns.grid(row=9, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Save", command=self._on_save).grid(row=0, column=1)

    # --- assistant: draft the requirement from the rough note, off the UI thread ---
    def _draft(self) -> None:
        note = self.statement.get("1.0", "end").strip()
        if not note:
            self.assist_status.config(text="Type a rough note first, then let the assistant polish it.")
            return
        if self.assistant is None or not self.assistant.available:
            why = getattr(self.assistant, "last_error", "assistant unavailable")
            self.assist_status.config(text=f"Assistant offline ({why}). You can still type it yourself.")
            return
        self.draft_btn.config(state="disabled")
        self.assist_status.config(text="Thinking… (first reply can take a moment)")

        def worker():
            result = self.assistant.draft_requirement(note, project_name="")
            # Hop back to the UI thread to touch widgets.
            self.after(0, lambda: self._apply_draft(result))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_draft(self, result) -> None:
        self.draft_btn.config(state="normal")
        if not result or not result.get("statement"):
            self.assist_status.config(text="Assistant couldn't draft that — try rewording, or type it yourself.")
            return
        self.statement.delete("1.0", "end")
        self.statement.insert("1.0", result["statement"])
        if result.get("acceptance_criteria"):
            self.accept.delete("1.0", "end")
            self.accept.insert("1.0", result["acceptance_criteria"])
        self.assist_status.config(text="Drafted by the local assistant — review and edit before saving.")

    def _on_save(self) -> None:
        statement = self.statement.get("1.0", "end").strip()
        if not statement:
            messagebox.showwarning("Missing statement", "Please enter the requirement.", parent=self)
            return
        self.result = {
            "statement": statement,
            "req_type": self.type_var.get(),
            "moscow": self.moscow_var.get(),
            "acceptance_criteria": self.accept.get("1.0", "end").strip(),
            "source": self.source_var.get().strip(),
        }
        self.destroy()


class SaveRequirementsDialog(tk.Toplevel):
    """Checklist to pick which of the assistant's proposed requirements to save."""

    def __init__(self, parent, statements: list[str]):
        super().__init__(parent)
        self.title("Save requirements")
        self.result: list[str] | None = None
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=16)
        frm.grid(sticky="nsew")
        ttk.Label(frm, text="The assistant proposed these. Check the ones to save:",
                  font=FONT_BOLD).grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.vars: list[tuple[tk.BooleanVar, str]] = []
        for i, s in enumerate(statements, start=1):
            var = tk.BooleanVar(value=True)  # all checked by default
            ttk.Checkbutton(frm, text=s, variable=var, wraplength=560).grid(
                row=i, column=0, sticky="w", pady=2)
            self.vars.append((var, s))

        btns = ttk.Frame(frm)
        btns.grid(row=len(statements) + 1, column=0, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=self.destroy).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Save checked", command=self._on_save).grid(row=0, column=1)

    def _on_save(self) -> None:
        self.result = [s for var, s in self.vars if var.get()]
        self.destroy()


class ScopeGuardDialog(tk.Toplevel):
    """Shows scope drift vs the latest baseline; lets you lock a new baseline."""

    ZONE_COLOR = {"GREEN": "#137333", "YELLOW": "#b06000", "RED": "#a50e0e"}

    def __init__(self, parent, conn, project_id: int):
        super().__init__(parent)
        self.title("Scope Guard")
        self.conn = conn
        self.project_id = project_id
        self.transient(parent)
        self.grab_set()

        frm = ttk.Frame(self, padding=16)
        frm.grid(sticky="nsew")
        ttk.Label(frm, text="🛡 Scope Guard — drift vs the baselined requirements",
                  font=FONT_BOLD).grid(row=0, column=0, sticky="w")
        self.report = tk.Text(frm, font=("Consolas", 11), width=74, height=16,
                              wrap="word", state="disabled")
        self.report.grid(row=1, column=0, sticky="nsew", pady=(8, 8))

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="e")
        ttk.Button(btns, text="🔒 Lock baseline now", command=self._lock).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Close", command=self.destroy).grid(row=0, column=1)
        self._render()

    def _render(self) -> None:
        base = db.get_latest_baseline(self.conn, self.project_id)
        current = db.list_requirements(self.conn, self.project_id)
        self.report.config(state="normal")
        self.report.delete("1.0", "end")
        if base is None:
            self.report.insert(
                "end",
                "No baseline locked yet.\n\n"
                "Lock a baseline to freeze the current requirement set as the agreed "
                "scope. After that, Scope Guard shows what's been added, removed, or "
                "changed — so the project can't quietly drift off-scope.")
        else:
            items = db.list_baseline_items(self.conn, base["id"])
            report = guardrail.check_drift(current, items)
            text = guardrail.summarize(report, base["created_at"])
            self.report.insert("end", text)
            # Colour the first line by zone.
            self.report.tag_add("zone", "1.0", "1.end")
            self.report.tag_config("zone", foreground=self.ZONE_COLOR.get(report["zone"], "black"),
                                   font=("Consolas", 12, "bold"))
        self.report.config(state="disabled")

    def _lock(self) -> None:
        db.lock_baseline(self.conn, self.project_id)
        self._render()


class ImprintApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Imprint {getattr(__import__('imprint'), '__version__', '')} — SDLC Paperwork, Local")
        self.geometry("1040x820")
        self.minsize(900, 640)

        self.conn = db.connect()
        db.init_schema(self.conn)
        self.current_project_id: int | None = None
        # One shared local assistant (checks Ollama once); reused by every dialog.
        self.assistant = assistant.RequirementAssistant()
        self.chat_history: list[dict] = []
        self._last_reply: str = ""

        self._build_ui()
        self._refresh_projects()

    def _build_ui(self) -> None:
        ttk.Label(self, text="Imprint", font=FONT_TITLE).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Label(self, text="Local-first SDLC paperwork — your requirements, stored once.",
                  font=FONT).pack(anchor="w", padx=16, pady=(0, 8))

        # Assistant docks at the bottom (packed first so 'bottom' wins the cavity).
        self._build_assistant().pack(side="bottom", fill="x", padx=16, pady=(0, 12))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # --- left: projects ---
        left = ttk.LabelFrame(body, text="Projects", padding=8)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self.projects_list = tk.Listbox(left, font=FONT, activestyle="dotbox")
        self.projects_list.grid(row=0, column=0, sticky="nsew")
        self.projects_list.bind("<<ListboxSelect>>", self._on_project_select)
        ttk.Button(left, text="+ New Project", command=self._new_project).grid(
            row=1, column=0, sticky="ew", pady=(8, 0))

        # --- right: requirements ---
        right = ttk.LabelFrame(body, text="Requirements", padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self.project_header = ttk.Label(right, text="Select or create a project.", font=FONT_BOLD)
        self.project_header.grid(row=0, column=0, sticky="w", pady=(0, 6))

        cols = ("key", "type", "priority", "status", "statement")
        self.req_tree = ttk.Treeview(right, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (85, 120, 80, 110, 430)):
            self.req_tree.heading(c, text=c.capitalize())
            self.req_tree.column(c, width=w, anchor="w")
        self.req_tree.grid(row=1, column=0, sticky="nsew")
        # Double-click a row to check it off (draft <-> baselined).
        self.req_tree.bind("<Double-1>", lambda _e: self._toggle_baseline())
        vs = ttk.Scrollbar(right, orient="vertical", command=self.req_tree.yview)
        self.req_tree.configure(yscrollcommand=vs.set)
        vs.grid(row=1, column=1, sticky="ns")

        actions = ttk.Frame(right)
        actions.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.add_req_btn = ttk.Button(actions, text="+ Add Requirement",
                                      command=self._add_requirement, state="disabled")
        self.add_req_btn.grid(row=0, column=0)
        self.gen_srs_btn = ttk.Button(actions, text="📄 Generate SRS (.docx)",
                                      command=self._generate_srs, state="disabled")
        self.gen_srs_btn.grid(row=0, column=1, padx=(8, 0))
        self.gen_matrix_btn = ttk.Button(actions, text="📊 Traceability Matrix (.xlsx)",
                                         command=self._generate_matrix, state="disabled")
        self.gen_matrix_btn.grid(row=0, column=2, padx=(8, 0))
        self.gen_stories_btn = ttk.Button(actions, text="📝 User Stories (.docx)",
                                          command=self._generate_stories, state="disabled")
        self.gen_stories_btn.grid(row=0, column=3, padx=(8, 0))
        self.baseline_btn = ttk.Button(actions, text="✓ Baseline / un-baseline",
                                       command=self._toggle_baseline, state="disabled")
        self.baseline_btn.grid(row=0, column=4, padx=(8, 0))
        self.guard_btn = ttk.Button(actions, text="🛡 Scope Guard",
                                    command=self._scope_guard, state="disabled")
        self.guard_btn.grid(row=1, column=0, sticky="w", pady=(6, 0))

    # --- assistant conversation panel ---
    def _build_assistant(self) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(
            self, text="🤖 Assistant — describe your project; I'll help draft requirements", padding=8)
        panel.columnconfigure(0, weight=1)

        self.chat_log = tk.Text(panel, font=FONT, height=9, wrap="word", state="disabled",
                                background="#f6f7f9")
        self.chat_log.grid(row=0, column=0, columnspan=3, sticky="nsew")
        cs = ttk.Scrollbar(panel, orient="vertical", command=self.chat_log.yview)
        self.chat_log.configure(yscrollcommand=cs.set)
        cs.grid(row=0, column=3, sticky="ns")

        self.chat_input = ttk.Entry(panel, font=FONT)
        self.chat_input.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.chat_input.bind("<Return>", lambda _e: self._chat_send())
        self.send_btn = ttk.Button(panel, text="Send", command=self._chat_send)
        self.send_btn.grid(row=1, column=1, padx=(8, 0), pady=(8, 0))
        self.save_reply_btn = ttk.Button(panel, text="➕ Save reply as requirement",
                                         command=self._save_reply_as_req, state="disabled")
        self.save_reply_btn.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        self.clear_chat_btn = ttk.Button(panel, text="🗑 Clear", command=self._clear_conversation,
                                         state="disabled")
        self.clear_chat_btn.grid(row=1, column=3, padx=(8, 0), pady=(8, 0))

        # Input stays locked until a project is picked — the conversation is
        # saved per-project, so it needs to know which project it belongs to.
        self.chat_input.config(state="disabled")
        self.send_btn.config(state="disabled")
        if self.assistant.available:
            self._chat_append("Assistant",
                              "Select or create a project, then tell me about it — "
                              "I'll help draft requirements and remember our conversation.")
        else:
            self._chat_append("Assistant",
                              f"(offline: {self.assistant.last_error}) "
                              "You can still add requirements manually.")
        return panel

    def _clear_chat_log(self) -> None:
        self.chat_log.config(state="normal")
        self.chat_log.delete("1.0", "end")
        self.chat_log.config(state="disabled")

    def _load_conversation(self) -> None:
        """Rebuild the chat panel from the selected project's saved conversation."""
        self._clear_chat_log()
        self.chat_history = []
        self._last_reply = ""
        if self.current_project_id is None:
            return
        if not self.assistant.available:
            self._chat_append("Assistant", f"(offline: {self.assistant.last_error})")
            return

        messages = db.list_chat_messages(self.conn, self.current_project_id)
        if not messages:
            self._chat_append("Assistant",
                              "Tell me about this project and what it needs to do, "
                              "and I'll help turn it into requirements.")
        else:
            for m in messages:
                self._chat_append("You" if m["role"] == "user" else "Assistant", m["content"])
                self.chat_history.append({"role": m["role"], "content": m["content"]})
                if m["role"] == "assistant":
                    self._last_reply = m["content"]

        self.chat_input.config(state="normal")
        self.send_btn.config(state="normal")
        self.clear_chat_btn.config(state="normal")
        self.save_reply_btn.config(state="normal" if self._last_reply else "disabled")

    def _clear_conversation(self) -> None:
        if self.current_project_id is None:
            return
        if not messagebox.askyesno("Clear conversation",
                                   "Delete the saved conversation for this project? "
                                   "(Your saved requirements are not affected.)"):
            return
        db.clear_chat_messages(self.conn, self.current_project_id)
        self._load_conversation()

    def _chat_append(self, who: str, text: str) -> None:
        self.chat_log.config(state="normal")
        self.chat_log.insert("end", f"{who}: {text}\n\n")
        self.chat_log.config(state="disabled")
        self.chat_log.see("end")

    def _chat_send(self) -> None:
        msg = self.chat_input.get().strip()
        if not msg or not self.assistant.available:
            return
        self.chat_input.delete(0, "end")
        self._chat_append("You", msg)
        self.chat_history.append({"role": "user", "content": msg})
        if self.current_project_id:
            db.add_chat_message(self.conn, self.current_project_id, "user", msg)
        self.send_btn.config(state="disabled", text="Thinking…")

        project = db.get_project(self.conn, self.current_project_id) if self.current_project_id else None
        pname = project["name"] if project else ""
        method = models.methodology_label(project["methodology"]) if project else ""

        def worker():
            reply = self.assistant.chat(self.chat_history, pname, method)
            self.after(0, lambda: self._chat_receive(reply))

        threading.Thread(target=worker, daemon=True).start()

    def _chat_receive(self, reply) -> None:
        self.send_btn.config(state="normal", text="Send")
        if not reply:
            self._chat_append("Assistant", f"(couldn't reach the model: {self.assistant.last_error})")
            return
        self._last_reply = reply
        self.chat_history.append({"role": "assistant", "content": reply})
        if self.current_project_id:
            db.add_chat_message(self.conn, self.current_project_id, "assistant", reply)
        self._chat_append("Assistant", reply)
        self.save_reply_btn.config(state="normal" if self.current_project_id else "disabled")

    def _save_reply_as_req(self) -> None:
        if not self._last_reply or self.current_project_id is None:
            return
        statements = assistant.extract_requirements(self._last_reply)
        if not statements:  # no canonical line — fall back to the single-line grab
            one = assistant.extract_requirement(self._last_reply)
            statements = [one] if one else []
        if not statements:
            messagebox.showinfo("Nothing to save",
                                "The assistant's last reply didn't contain a clear requirement.")
            return

        # One requirement saves straight away; several open the checkbox picker.
        if len(statements) == 1:
            chosen = statements
        else:
            dlg = SaveRequirementsDialog(self, statements)
            self.wait_window(dlg)
            chosen = dlg.result
            if not chosen:
                return

        saved = []
        for statement in chosen:
            try:
                row = db.add_requirement(self.conn, self.current_project_id, "Functional", statement)
                saved.append(row["req_key"])
            except ValueError:
                pass
        self._refresh_requirements()
        if saved:
            self._chat_append("Imprint", f"✓ Saved {len(saved)} requirement(s): {', '.join(saved)}")

    # --- projects ---
    def _refresh_projects(self) -> None:
        self.projects_list.delete(0, "end")
        self._projects = db.list_projects(self.conn)
        for p in self._projects:
            self.projects_list.insert("end", f"{p['name']}  ·  {models.methodology_label(p['methodology'])}")

    def _new_project(self) -> None:
        dlg = ProjectDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            name, key, desc = dlg.result
            try:
                db.create_project(self.conn, name, key, desc)
            except ValueError as e:
                messagebox.showerror("Could not create project", str(e))
                return
            self._refresh_projects()

    def _on_project_select(self, _event=None) -> None:
        sel = self.projects_list.curselection()
        if not sel:
            return
        project = self._projects[sel[0]]
        self.current_project_id = project["id"]
        self.project_header.config(
            text=f"{project['name']}  —  {models.methodology_label(project['methodology'])}")
        self.add_req_btn.config(state="normal")
        self.gen_srs_btn.config(state="normal")
        self.gen_matrix_btn.config(state="normal")
        self.gen_stories_btn.config(state="normal")
        self.baseline_btn.config(state="normal")
        self.guard_btn.config(state="normal")
        self._refresh_requirements()
        self._load_conversation()  # per-project saved conversation resumes here

    # --- requirements ---
    @staticmethod
    def _status_display(status: str) -> str:
        # A clear check-off indicator so nothing looks half-done.
        return "✓ baselined" if status == "baselined" else status

    def _refresh_requirements(self) -> None:
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)
        if self.current_project_id is None:
            return
        for r in db.list_requirements(self.conn, self.current_project_id):
            # iid = requirement id, so a double-click / button can look it up.
            self.req_tree.insert("", "end", iid=str(r["id"]), values=(
                r["req_key"], r["req_type"], r["moscow"],
                self._status_display(r["status"]), r["statement"]))

    def _scope_guard(self) -> None:
        if self.current_project_id is None:
            return
        dlg = ScopeGuardDialog(self, self.conn, self.current_project_id)
        self.wait_window(dlg)

    def _toggle_baseline(self) -> None:
        """Check off (baseline) or un-check the selected requirement(s)."""
        selection = self.req_tree.selection()
        if not selection:
            return
        for iid in selection:
            row = self.conn.execute(
                "SELECT status FROM requirements WHERE id = ?", (int(iid),)).fetchone()
            if row is None:
                continue
            new_status = "draft" if row["status"] == "baselined" else "baselined"
            db.set_requirement_status(self.conn, int(iid), new_status)
        self._refresh_requirements()

    def _add_requirement(self) -> None:
        if self.current_project_id is None:
            return
        dlg = RequirementDialog(self, self.assistant)
        self.wait_window(dlg)
        if dlg.result:
            try:
                db.add_requirement(self.conn, self.current_project_id, **dlg.result)
            except ValueError as e:
                messagebox.showerror("Could not add requirement", str(e))
                return
            self._refresh_requirements()

    def _generate_srs(self) -> None:
        if self.current_project_id is None:
            return
        project = db.get_project(self.conn, self.current_project_id)
        requirements = db.list_requirements(self.conn, self.current_project_id)
        suggested = srs.default_output_path(project["name"])
        out_path = filedialog.asksaveasfilename(
            title="Save SRS", defaultextension=".docx",
            initialfile=os.path.basename(suggested),
            initialdir=os.path.dirname(suggested),
            filetypes=[("Word document", "*.docx")],
        )
        if not out_path:
            return
        try:
            srs.build_srs(project, requirements, out_path)
        except Exception as e:  # rendering failure shouldn't crash the app
            messagebox.showerror("Could not generate SRS", str(e))
            return
        if messagebox.askyesno("SRS generated", f"Saved:\n{out_path}\n\nOpen it now?"):
            try:
                os.startfile(out_path)  # Windows: open in the default word processor
            except Exception:
                pass

    def _generate_matrix(self) -> None:
        if self.current_project_id is None:
            return
        project = db.get_project(self.conn, self.current_project_id)
        requirements = db.list_requirements(self.conn, self.current_project_id)
        suggested = traceability.default_matrix_path(project["name"])
        out_path = filedialog.asksaveasfilename(
            title="Save Traceability Matrix", defaultextension=".xlsx",
            initialfile=os.path.basename(suggested),
            initialdir=os.path.dirname(suggested),
            filetypes=[("Excel workbook", "*.xlsx")],
        )
        if not out_path:
            return
        try:
            traceability.build_traceability_xlsx(project, requirements, out_path)
        except Exception as e:
            messagebox.showerror("Could not generate matrix", str(e))
            return
        if messagebox.askyesno("Traceability matrix generated", f"Saved:\n{out_path}\n\nOpen it now?"):
            try:
                os.startfile(out_path)
            except Exception:
                pass

    def _generate_stories(self) -> None:
        if self.current_project_id is None:
            return
        project = db.get_project(self.conn, self.current_project_id)
        requirements = db.list_requirements(self.conn, self.current_project_id)
        suggested = user_stories.default_output_path(project["name"])
        out_path = filedialog.asksaveasfilename(
            title="Save User Stories", defaultextension=".docx",
            initialfile=os.path.basename(suggested),
            initialdir=os.path.dirname(suggested),
            filetypes=[("Word document", "*.docx")],
        )
        if not out_path:
            return
        try:
            user_stories.build_user_stories(project, requirements, out_path)
        except Exception as e:
            messagebox.showerror("Could not generate user stories", str(e))
            return
        if messagebox.askyesno("User stories generated", f"Saved:\n{out_path}\n\nOpen it now?"):
            try:
                os.startfile(out_path)
            except Exception:
                pass


def main() -> None:
    _enable_dpi_awareness()
    ImprintApp().mainloop()


if __name__ == "__main__":
    main()
