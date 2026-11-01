# ovpn_keypass

A small, pure-Python tool to **change, add, or remove the password** on
the private key embedded (as `<key>...</key>`) inside an OpenVPN client
`.ovpn` config file. Works the same way on Windows, Linux, and macOS.

It does **not** support configs that reference an external key file
(a `key something.key` line with no inline `<key>` block) — only the
embedded-key case.

## Requirements

- Python 3.9+
- The [`cryptography`](https://pypi.org/project/cryptography/) package:

  ```bash
  pip install -r requirements.txt
  ```

- (GUI only) Tk support for Python — bundled with the official
  python.org installers for Windows and macOS. On Linux you may need
  to install it separately, e.g. `sudo apt install python3-tk`.

## Command-line usage

```bash
# Just check whether the embedded key currently has a password
python3 ovpn_keypass.py client.ovpn --info

# Add a password to a currently unencrypted key (prompts securely)
python3 ovpn_keypass.py client.ovpn --new-password

# Change an existing password (prompts for both old and new)
python3 ovpn_keypass.py client.ovpn --old-password --new-password

# Remove the password, leaving the key unencrypted
python3 ovpn_keypass.py client.ovpn --old-password oldpass --remove-password

# Write the result to a different file instead of editing in place
python3 ovpn_keypass.py client.ovpn --new-password newpass --output client-protected.ovpn
```

Notes:

- `--new-password` / `-n` and `--old-password` / `-p` can be given a
  value directly (`--new-password mypass`), but if you leave the value
  off, you'll be prompted securely instead (recommended — passwords
  typed on the command line can end up in your shell history).
- When editing a file in place, the original is backed up to
  `client.ovpn.bak` unless you pass `--no-backup`.
- Run `python3 ovpn_keypass.py --help` for the full option list.

## GUI usage

```bash
python3 ovpn_keypass_gui.py
```

Pick the `.ovpn` file, fill in the current password (if any) and the
new one (or choose "Remove password"), and click **Apply**. The
original file is backed up alongside it as `*.bak`.

## Building a standalone executable

To hand the tool to someone without a Python install, package it with
[PyInstaller](https://pyinstaller.org/) **on each target OS** (PyInstaller
does not cross-compile — build the Windows .exe on Windows, the macOS
app on macOS, etc.):

```bash
pip install pyinstaller

# CLI
pyinstaller --onefile ovpn_keypass.py

# GUI (no console window)
pyinstaller --onefile --windowed ovpn_keypass_gui.py
```

The resulting binary will be in `dist/`.

## How it works

- The tool looks for the inline `<key>...</key>` block in the `.ovpn`
  file and reads the PEM-encoded private key inside it.
- It detects whether the key is currently encrypted (presence of
  `ENCRYPTED` / `Proc-Type: 4,ENCRYPTED` in the PEM header), decrypts it
  with the old password if needed, then re-serializes it in PKCS#8 PEM
  format — encrypted with the new password, or unencrypted if removing
  the password.
- Everything else in the `.ovpn` file (certs, CA, options, etc.) is left
  untouched; only the text between `<key>` and `</key>` is replaced.
