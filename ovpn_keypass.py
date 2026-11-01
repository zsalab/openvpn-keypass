#!/usr/bin/env python3
"""
ovpn_keypass - change, add, or remove the password on the private key
embedded inside an OpenVPN client .ovpn config file.

Works on Windows, Linux, and macOS (pure Python + the `cryptography`
package). Only the <key>...</key> block embedded directly in the .ovpn
file is handled; configs that reference an external key file (via a
`key some.key` line and no <key> block) are not modified.

Library functions in this module are reused by the CLI (below) and by
ovpn_keypass_gui.py.
"""

from __future__ import annotations

import argparse
import getpass
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization

KEY_BLOCK_RE = re.compile(r"<key>\r?\n(.*?)\r?\n</key>", re.DOTALL)


class OvpnKeyError(Exception):
    """Raised for any expected, user-facing failure."""


def find_embedded_key_block(config_text: str) -> re.Match | None:
    """Return the regex match for the <key>...</key> block, or None."""
    return KEY_BLOCK_RE.search(config_text)


def is_encrypted_pem(pem_text: str) -> bool:
    """Heuristic check: does this PEM block look password-protected?"""
    return "ENCRYPTED" in pem_text or "Proc-Type: 4,ENCRYPTED" in pem_text


def load_private_key(pem_bytes: bytes, password: str | None):
    """Load a PEM private key, raising OvpnKeyError on a bad/missing password."""
    pwd_bytes = password.encode("utf-8") if password else None
    try:
        return serialization.load_pem_private_key(pem_bytes, password=pwd_bytes)
    except TypeError as exc:
        # cryptography raises TypeError when a password is required but
        # none was given, or when one was given but the key isn't encrypted.
        if "password" in str(exc).lower():
            raise OvpnKeyError(
                "A password is required to read this key but none was given."
                if pwd_bytes is None
                else "This key is not encrypted; no password should be given."
            ) from exc
        raise OvpnKeyError(f"Could not read private key: {exc}") from exc
    except ValueError as exc:
        raise OvpnKeyError(f"Could not read private key (wrong password?): {exc}") from exc


def serialize_private_key(key_obj, new_password: str | None) -> bytes:
    """Serialize a private key back to PEM, encrypted with new_password or not."""
    if new_password:
        encryption = serialization.BestAvailableEncryption(new_password.encode("utf-8"))
    else:
        encryption = serialization.NoEncryption()
    return key_obj.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )


def rekey_config_text(
    config_text: str,
    old_password: str | None,
    new_password: str | None,
) -> tuple[str, bool]:
    """
    Re-key the embedded private key inside an .ovpn config's text.

    Returns (new_config_text, was_encrypted_before).
    Raises OvpnKeyError if there's no embedded key, or the password is wrong.
    """
    match = find_embedded_key_block(config_text)
    if not match:
        raise OvpnKeyError(
            "No embedded <key>...</key> block found in this file. "
            "This tool only supports configs with an inline private key; "
            "a config that references an external key file (e.g. a 'key "
            "some.key' line) is not supported."
        )

    old_pem = match.group(1).strip() + "\n"
    was_encrypted = is_encrypted_pem(old_pem)

    key_obj = load_private_key(old_pem.encode("utf-8"), old_password if was_encrypted else None)
    new_pem = serialize_private_key(key_obj, new_password).decode("utf-8").rstrip("\n")

    new_block = f"<key>\n{new_pem}\n</key>"
    new_text = config_text[: match.start()] + new_block + config_text[match.end() :]
    return new_text, was_encrypted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _prompt_password(prompt: str, confirm: bool = False) -> str:
    while True:
        pwd = getpass.getpass(prompt)
        if confirm:
            pwd2 = getpass.getpass("Confirm new password: ")
            if pwd != pwd2:
                print("Passwords did not match, try again.\n", file=sys.stderr)
                continue
        return pwd


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ovpn_keypass",
        description="Change, add, or remove the password on the private key "
        "embedded in an OpenVPN client .ovpn file.",
    )
    parser.add_argument("config", help="Path to the .ovpn client config file")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--new-password",
        "-n",
        nargs="?",
        const="",
        metavar="PASSWORD",
        help="Set/change the key's password. If given with no value, you "
        "will be prompted securely (recommended, so the password doesn't "
        "end up in your shell history).",
    )
    mode.add_argument(
        "--remove-password",
        action="store_true",
        help="Remove the password, leaving the embedded key unencrypted.",
    )
    mode.add_argument(
        "--info",
        action="store_true",
        help="Just report whether the embedded key is currently encrypted; "
        "don't change anything.",
    )

    parser.add_argument(
        "--old-password",
        "-p",
        metavar="PASSWORD",
        help="The key's current password, if it has one. If the key is "
        "encrypted and this is omitted, you will be prompted securely.",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="FILE",
        help="Write the result to FILE instead of modifying the config in place.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="When modifying in place, don't keep a .bak copy of the original.",
    )
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config_path = Path(args.config)

    try:
        config_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: could not read '{config_path}': {exc}", file=sys.stderr)
        return 1

    if args.info:
        match = find_embedded_key_block(config_text)
        if not match:
            print("No embedded <key> block found in this config.")
            return 0
        encrypted = is_encrypted_pem(match.group(1))
        print(f"Embedded key is {'password-protected' if encrypted else 'NOT password-protected'}.")
        return 0

    # Figure out the old password, prompting only if the key turns out encrypted.
    old_password = args.old_password
    if old_password is None:
        match = find_embedded_key_block(config_text)
        if match and is_encrypted_pem(match.group(1)):
            old_password = _prompt_password("Current key password: ")

    if args.remove_password:
        new_password = None
    else:
        new_password = args.new_password
        if new_password == "":
            new_password = _prompt_password("New key password: ", confirm=True)
            if not new_password:
                print("error: an empty new password isn't allowed; use --remove-password instead.", file=sys.stderr)
                return 1

    attempts_left = 3
    while True:
        try:
            new_text, _ = rekey_config_text(config_text, old_password, new_password)
            break
        except OvpnKeyError as exc:
            attempts_left -= 1
            if "password" in str(exc).lower() and attempts_left > 0 and args.old_password is None:
                print(f"{exc} ({attempts_left} attempt(s) left)", file=sys.stderr)
                old_password = _prompt_password("Current key password: ")
                continue
            print(f"error: {exc}", file=sys.stderr)
            return 1

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(new_text, encoding="utf-8")
        print(f"Wrote updated config to '{out_path}'.")
    else:
        if not args.no_backup:
            backup_path = config_path.with_suffix(config_path.suffix + ".bak")
            backup_path.write_text(config_text, encoding="utf-8")
            print(f"Backed up original to '{backup_path}'.")
        config_path.write_text(new_text, encoding="utf-8")
        print(f"Updated '{config_path}' in place.")

    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
