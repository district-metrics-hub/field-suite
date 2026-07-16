#!/usr/bin/env python3
"""sign_release.py -- BUILD-TIME release signer (DRAFT).

Runs in the NEUTRAL org's release pipeline (GitHub Actions), NOT in the shipped
app. Given the built installer + a version + notes + the private signing key, it:

  1. computes the installer's SHA-256,
  2. builds the `latest.json` object,
  3. signs the CANONICAL bytes (json-minus-signature) with Ed25519,
  4. writes the signed `latest.json`.

It also generates a keypair (`--genkey`) so you never have to touch openssl.

  latest.json schema produced:
    {
      "version": "1.2.0",
      "notes": "...",
      "installer_url": "https://github.com/<ORG>/<REPO>/releases/latest/download/UhaulSuiteSetup.exe",
      "sha256": "<hex>",
      "signature": "<base64 ed25519 sig over canonical json-minus-signature>"
    }

CANONICALIZATION MUST MATCH THE APP. The app verifies over:
    json.dumps({...without "signature"...}, sort_keys=True,
               separators=(",", ":"), ensure_ascii=False).encode("utf-8")
`canonical_bytes()` below is byte-identical to updater.canonical_bytes(). If you
change one, change both, or every client will reject every release.

DEPENDENCIES: none required. This reuses the same vendored `ed25519_pure.py`
as the app, so CI needs no pip install. (If you'd rather sign with a hardened
lib, see the `cryptography`/openssl notes at the bottom -- the 64-byte
signature is identical either way.)

=============================================================================
KEYGEN + SECRET STORAGE  (do this ONCE, keep the private key OFF every repo)
=============================================================================

  # 1. Generate a keypair (prints both keys, base64):
  python sign_release.py --genkey

  # -> PRIVATE (seed) base64:  <32-byte seed, base64>      # SECRET
  # -> PUBLIC        base64:   <32-byte pubkey, base64>     # bake into app

  # 2. Bake the PUBLIC key into the shipped app:
  #    paste it into updater.PUBKEY_B64 (or config "updates.pubkey_b64").
  #    The public key is safe to commit -- that's the whole point.

  # 3. Store the PRIVATE key as a GitHub Actions secret in the NEUTRAL repo:
  gh secret set ED25519_PRIVATE_KEY_B64 --repo <ORG>/<REPO> --body "<seed base64>"
  #    (or Settings -> Secrets and variables -> Actions -> New repository secret,
  #     name = ED25519_PRIVATE_KEY_B64). NEVER commit it. NEVER echo it in logs.

  # ALTERNATIVE keygen without this script (equivalent 32-byte seed):
  #   python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
  #   then derive the public key:  python sign_release.py --pubkey "<seed b64>"

Rotating the key = generate a new pair, re-bake the public key, ship a new app
build, and swap the Actions secret. Old installs keep trusting the old key until
they update -- so rotate rarely and deliberately.
"""

import argparse
import base64
import hashlib
import json
import os
import sys

# Same vendored module the app ships. Keep this file next to a copy of
# ed25519_pure.py in the release repo (or vendor it via a submodule).
import ed25519_pure

# TODO(build): the neutral org/repo. Used only to construct the default
# installer_url; override with --installer-url if your asset name differs.
ORG = "district-metrics-hub"
REPO = "field-suite"
DEFAULT_ASSET = "UhaulSuiteSetup.exe"


def canonical_bytes(latest_json: dict) -> bytes:
    """MUST match updater.canonical_bytes() byte-for-byte."""
    payload = {k: v for k, v in latest_json.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def default_installer_url(org: str, repo: str, asset: str) -> str:
    return "https://github.com/%s/%s/releases/latest/download/%s" % (org, repo, asset)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_genkey(_args) -> int:
    seed = os.urandom(32)
    pub = ed25519_pure.publickey(seed)
    print("PRIVATE (seed) base64:  " + base64.b64encode(seed).decode())
    print("PUBLIC         base64:  " + base64.b64encode(pub).decode())
    print()
    print("-> Store PRIVATE as GH secret ED25519_PRIVATE_KEY_B64 (never commit).")
    print("-> Bake PUBLIC into updater.PUBKEY_B64.")
    return 0


def cmd_pubkey(args) -> int:
    """Derive+print the public key from a seed (to re-bake without regenerating)."""
    seed = base64.b64decode(args.seed_b64)
    if len(seed) != 32:
        print("error: seed must decode to 32 bytes", file=sys.stderr)
        return 2
    print(base64.b64encode(ed25519_pure.publickey(seed)).decode())
    return 0


def cmd_sign(args) -> int:
    # --- private key: from --key-b64, else env ED25519_PRIVATE_KEY_B64 (CI) ---
    seed_b64 = args.key_b64 or os.environ.get("ED25519_PRIVATE_KEY_B64", "")
    seed_b64 = seed_b64.strip()
    if not seed_b64:
        print("error: no private key (pass --key-b64 or set "
              "ED25519_PRIVATE_KEY_B64)", file=sys.stderr)
        return 2
    try:
        seed = base64.b64decode(seed_b64)
    except Exception:  # noqa: BLE001
        print("error: --key-b64 is not valid base64", file=sys.stderr)
        return 2
    if len(seed) != 32:
        print("error: private key must decode to 32 bytes", file=sys.stderr)
        return 2

    if not os.path.isfile(args.installer):
        print("error: installer not found: %s" % args.installer, file=sys.stderr)
        return 2

    digest = sha256_file(args.installer)
    installer_url = args.installer_url or default_installer_url(
        args.org, args.repo, os.path.basename(args.installer) or DEFAULT_ASSET)

    # notes: literal string or @file
    notes = args.notes or ""
    if notes.startswith("@"):
        with open(notes[1:], "r", encoding="utf-8") as f:
            notes = f.read().strip()

    latest = {
        "version": args.version.strip().lstrip("vV"),
        "notes": notes,
        "installer_url": installer_url,
        "sha256": digest,
    }

    pub = ed25519_pure.publickey(seed)
    sig = ed25519_pure.sign(canonical_bytes(latest), seed, pub)
    latest["signature"] = base64.b64encode(sig).decode()

    # self-check: verify what we just signed before we ship it (catches a
    # canonicalization mismatch in CI instead of on every client).
    from_verify = ed25519_pure.verify(sig, canonical_bytes(latest), pub)
    if not from_verify:
        print("error: self-verify FAILED -- refusing to write a bad latest.json",
              file=sys.stderr)
        return 3

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(latest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print("wrote %s" % args.out)
    print("  version:       %s" % latest["version"])
    print("  sha256:        %s" % digest)
    print("  installer_url: %s" % installer_url)
    print("  public key:    %s" % base64.b64encode(pub).decode())
    print("  self-verify:   OK")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Build-time Ed25519 release signer.")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("genkey", help="generate a new ed25519 keypair (base64)")

    pk = sub.add_parser("pubkey", help="derive public key from a seed")
    pk.add_argument("seed_b64", help="base64 private seed")

    sg = sub.add_parser("sign", help="build + sign latest.json")
    sg.add_argument("--installer", required=True, help="path to UhaulSuiteSetup.exe")
    sg.add_argument("--version", required=True, help="release version, e.g. 1.2.0")
    sg.add_argument("--notes", default="", help="release notes, or @path/to/notes.md")
    sg.add_argument("--out", default="latest.json", help="output path")
    sg.add_argument("--org", default=ORG)
    sg.add_argument("--repo", default=REPO)
    sg.add_argument("--installer-url", default="",
                    help="override the installer_url (default = latest/download/<asset>)")
    sg.add_argument("--key-b64", default="",
                    help="private seed base64 (else env ED25519_PRIVATE_KEY_B64)")

    # convenience: allow `--genkey` as a flag too (matches the docstring usage)
    p.add_argument("--genkey", action="store_true", help=argparse.SUPPRESS)

    args = p.parse_args(argv)
    if getattr(args, "genkey", False) and not args.cmd:
        return cmd_genkey(args)
    if args.cmd == "genkey":
        return cmd_genkey(args)
    if args.cmd == "pubkey":
        return cmd_pubkey(args)
    if args.cmd == "sign":
        return cmd_sign(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())


# =============================================================================
# ALTERNATIVE: sign with `cryptography` (build-time only) instead of the
# vendored pure-python signer. The 64-byte signature is identical.
#
#   from cryptography.hazmat.primitives.asymmetric.ed25519 import (
#       Ed25519PrivateKey, Ed25519PublicKey)
#   sk = Ed25519PrivateKey.from_private_bytes(seed)          # seed = 32 bytes
#   sig = sk.sign(canonical_bytes(latest))                    # 64 bytes
#   pub = sk.public_key().public_bytes_raw()                  # 32 bytes
#
# openssl can also generate a raw seed, but its PEM/DER wrapping is fiddly to
# convert to the 32-byte raw seed this pipeline uses -- prefer --genkey or the
# one-liner in the docstring.
# =============================================================================
