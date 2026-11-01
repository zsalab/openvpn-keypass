#!/usr/bin/env python3
"""
Minimal cross-platform GUI for ovpn_keypass.py (Windows / Linux / macOS).

Lets a user pick an .ovpn file, enter the current password (if any) and
a new one, and then change/add/remove the password on the embedded
private key. Requires Python's bundled tkinter (included with the
python.org installers for Windows/macOS; on Linux install the
`python3-tk` package if it's missing).
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ovpn_keypass import OvpnKeyError, find_embedded_key_block, is_encrypted_pem, rekey_config_text


class App(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.master = master
        master.title("OpenVPN Key Password Tool")
        master.resizable(False, False)
        self.pack(fill="both", expand=True)

        self.config_path: str = ""
        self.action = tk.StringVar(value="change")

        self._build_file_row()
        self._build_password_rows()
        self._build_action_row()
        self._build_buttons()
        self._build_status_row()

    # -- widgets ----------------------------------------------------------

    def _build_file_row(self) -> None:
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="Config file (.ovpn):").pack(anchor="w")

        picker = ttk.Frame(row)
        picker.pack(fill="x")
        self.file_entry = ttk.Entry(picker, width=48)
        self.file_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(picker, text="Browse…", command=self._browse).pack(side="left", padx=(6, 0))

    def _build_password_rows(self) -> None:
        grid = ttk.Frame(self)
        grid.pack(fill="x", pady=(0, 8))

        ttk.Label(grid, text="Current password (leave blank if none):").grid(row=0, column=0, sticky="w")
        self.old_pw_entry = ttk.Entry(grid, show="*", width=32)
        self.old_pw_entry.grid(row=1, column=0, sticky="we", pady=(0, 6))

        ttk.Label(grid, text="New password:").grid(row=2, column=0, sticky="w")
        self.new_pw_entry = ttk.Entry(grid, show="*", width=32)
        self.new_pw_entry.grid(row=3, column=0, sticky="we")

    def _build_action_row(self) -> None:
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(8, 8))
        ttk.Radiobutton(
            row, text="Set / change password", variable=self.action, value="change",
            command=self._sync_action,
        ).pack(anchor="w")
        ttk.Radiobutton(
            row, text="Remove password (make key unencrypted)", variable=self.action, value="remove",
            command=self._sync_action,
        ).pack(anchor="w")

    def _build_buttons(self) -> None:
        row = ttk.Frame(self)
        row.pack(fill="x", pady=(4, 0))
        ttk.Button(row, text="Apply", command=self._apply).pack(side="right")

    def _build_status_row(self) -> None:
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, foreground="#555").pack(fill="x", pady=(8, 0))

    # -- behavior -----------------------------------------------------------

    def _sync_action(self) -> None:
        removing = self.action.get() == "remove"
        self.new_pw_entry.configure(state="disabled" if removing else "normal")

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose an OpenVPN config file",
            filetypes=[("OpenVPN config", "*.ovpn *.conf"), ("All files", "*.*")],
        )
        if path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, path)
            self._check_status(path)

    def _check_status(self, path: str) -> None:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            self.status_var.set(f"Could not read file: {exc}")
            return
        match = find_embedded_key_block(text)
        if not match:
            self.status_var.set("No embedded <key> block found in this file.")
        else:
            encrypted = is_encrypted_pem(match.group(1))
            self.status_var.set(
                "Embedded key is currently password-protected."
                if encrypted
                else "Embedded key is currently NOT password-protected."
            )

    def _apply(self) -> None:
        path_str = self.file_entry.get().strip()
        if not path_str:
            messagebox.showerror("Missing file", "Choose an .ovpn config file first.")
            return
        config_path = Path(path_str)
        if not config_path.is_file():
            messagebox.showerror("File not found", f"'{config_path}' does not exist.")
            return

        old_password = self.old_pw_entry.get() or None
        removing = self.action.get() == "remove"
        new_password = None if removing else (self.new_pw_entry.get() or None)

        if not removing and not new_password:
            messagebox.showerror("Missing password", "Enter a new password, or choose 'Remove password'.")
            return

        try:
            config_text = config_path.read_text(encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Read error", str(exc))
            return

        try:
            new_text, _ = rekey_config_text(config_text, old_password, new_password)
        except OvpnKeyError as exc:
            messagebox.showerror("Could not update key", str(exc))
            return

        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        try:
            backup_path.write_text(config_text, encoding="utf-8")
            config_path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror("Write error", str(exc))
            return

        self.old_pw_entry.delete(0, "end")
        self.new_pw_entry.delete(0, "end")
        self._check_status(str(config_path))
        messagebox.showinfo(
            "Done",
            f"Updated '{config_path.name}'.\nOriginal backed up to '{backup_path.name}'.",
        )


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
