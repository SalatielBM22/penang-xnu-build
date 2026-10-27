#!/usr/bin/env python3
"""Decide whether `pkgutil --check-signature` output proves an Apple-signed package.

Accepts only when (1) pkgutil reports a valid signature status and (2) the last certificate of the chain is
"Apple Root CA" with the pinned SHA-256 fingerprint below. Reads the pkgutil text on stdin; exit 0 = trusted.
"""
import re
import sys

APPLE_ROOT_CA_SHA256 = "B0B1730ECBC7FF4505142C49F1295E6EDA6BCAED7E2C68C5BE91B5A11001F024"
VALID_STATUS = ("signed Apple Software", "signed by a certificate trusted by")


def verdict(text: str) -> tuple[bool, str]:
    status = re.search(r"^\s*Status:\s*(.+)$", text, re.M)
    if not status or not status.group(1).strip().startswith(VALID_STATUS):
        return False, f"status not trusted: {status.group(1).strip() if status else 'missing'}"
    certs = re.split(r"^\s*\d+\.\s+", text.split("Certificate Chain:", 1)[-1], flags=re.M)[1:]
    if not certs:
        return False, "no certificate chain"
    root = certs[-1]
    name = root.splitlines()[0].strip()
    fp = re.search(r"SHA256 Fingerprint:\s*((?:[0-9A-F]{2}\s*)+)", root)
    fp_hex = re.sub(r"\s+", "", fp.group(1)) if fp else ""
    if name != "Apple Root CA" or fp_hex != APPLE_ROOT_CA_SHA256:
        return False, f"chain root is '{name}' with fingerprint {fp_hex or 'missing'}"
    return True, f"trusted: {status.group(1).strip()}; root Apple Root CA {fp_hex}"


if __name__ == "__main__":
    ok, why = verdict(sys.stdin.read())
    print(("TRUSTED " if ok else "REFUSED ") + why)
    sys.exit(0 if ok else 1)
