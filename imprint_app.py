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

from imprint import db, models, srs, assistant

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


class ImprintApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Imprint {getattr(__import__('imprint'), '__version__', '')} — SDLC Paperwork, Local")
        self.geometry("1040x660")
        self.minsize(880, 560)

        self.conn = db.connect()
        db.init_schema(self.conn)
        self.current_project_id: int | None = None
        # One shared local assistant (checks Ollama once); reused by every dialog.
        self.assistant = assistant.RequirementAssistant()

        self._build_ui()
        self._refresh_projects()

    def _build_ui(self) -> None:
        ttk.Label(self, text="Imprint", font=FONT_TITLE).pack(anchor="w", padx=16, pady=(12, 0))
        ttk.Label(self, text="Local-first SDLC paperwork — your requirements, stored once.",
                  font=FONT).pack(anchor="w", padx=16, pady=(0, 8))

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

        cols = ("key", "type", "priority", "statement")
        self.req_tree = ttk.Treeview(right, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (90, 130, 90, 520)):
            self.req_tree.heading(c, text=c.capitalize())
            self.req_tree.column(c, width=w, anchor="w")
        self.req_tree.grid(row=1, column=0, sticky="nsew")
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
        self._refresh_requirements()

    # --- requirements ---
    def _refresh_requirements(self) -> None:
        for item in self.req_tree.get_children():
            self.req_tree.delete(item)
        if self.current_project_id is None:
            return
        for r in db.list_requirements(self.conn, self.current_project_id):
            self.req_tree.insert("", "end", values=(
                r["req_key"], r["req_type"], r["moscow"], r["statement"]))

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


def main() -> None:
    _enable_dpi_awareness()
    ImprintApp().mainloop()


if __name__ == "__main__":
    main()
