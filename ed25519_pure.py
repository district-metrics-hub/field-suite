"""ed25519_pure.py -- VENDORED, dependency-free Ed25519 (RFC 8032).

WHY THIS FILE EXISTS
--------------------
The MCP Dashboard ships with only Flask as a runtime dependency (see
mcp-dashboard/requirements.txt -- it is literally one line: `flask>=3.0.0`).
The update-notification system must VERIFY an Ed25519 signature on `latest.json`
before it trusts anything downloaded from the internet. Python 3.12 has no
stdlib Ed25519, so our options were:

  (a) add `cryptography` as a NEW runtime dependency to every skill that ships,
      or
  (b) vendor a tiny pure-python verify (this file) -- ZERO new runtime deps.

We chose (b). Reasoning / tradeoff is documented in README.md, but in short:
this code runs ONCE per update poll (default every few hours), verifying a
~1 KB JSON blob. Pure-python Ed25519 verify of one small message is a few
milliseconds -- performance is a non-issue here -- and avoiding a compiled
dependency keeps the installer small, keeps the anonymous release pipeline
simple, and removes a supply-chain surface. `cryptography` would only be worth
it if we were verifying thousands of signatures per second.

PROVENANCE
----------
This is the well-known **public-domain** reference implementation of Ed25519
from Daniel J. Bernstein et al. (ed25519.cr.yp.to / the "slow, obviously
correct" reference in RFC 8032 Appendix A), lightly cleaned up for Python 3
(bytes instead of ints for hashing, minor style). It is intentionally the
REFERENCE implementation, not an optimized one -- correctness over speed.

  * It is NOT constant-time. That is FINE for *verification* with a *public*
    key over *public* data (there is no secret to leak on the verify path).
  * Signing IS also provided (used by the build-time signer, sign_release.py),
    and there the secret seed is handled in CI only. If you are paranoid about
    side channels in CI, sign with `cryptography`/`openssl` instead (see
    sign_release.py) -- the signature is byte-identical either way.

KEY / SIGNATURE ENCODING (what we bake + ship)
----------------------------------------------
  * private key = a 32-byte SEED (RFC 8032 calls it the secret key). We store
    it base64 in a GitHub Actions secret. NEVER shipped.
  * public key  = 32 bytes (`publickey(seed)`), base64, BAKED into the app.
  * signature   = 64 bytes (`sign(msg, seed, pub)`), base64, put in latest.json.

TODO(build): after you generate a keypair (sign_release.py --genkey), paste the
base64 PUBLIC key into updater.PUBKEY_B64.
"""

import hashlib

# ---- curve constants (RFC 8032, edwards25519) --------------------------------

b = 256
q = 2 ** 255 - 19
# group order l
l = 2 ** 252 + 27742317777372353535851937790883648493


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _expmod(base: int, e: int, m: int) -> int:
    # pow() is the fast, iterative C implementation -- no Python recursion depth
    # worries, and considerably faster than the reference's recursive expmod.
    return pow(base, e, m)


def _inv(x: int) -> int:
    return _expmod(x, q - 2, q)


d = -121665 * _inv(121666) % q
I = _expmod(2, (q - 1) // 4, q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(d * y * y + 1)
    x = _expmod(xx, (q + 3) // 8, q)
    if (x * x - xx) % q != 0:
        x = (x * I) % q
    if x % 2 != 0:
        x = q - x
    return x


By = 4 * _inv(5) % q
Bx = _xrecover(By)
B = [Bx % q, By % q]


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - d * x1 * x2 * y1 * y2)
    return [x3 % q, y3 % q]


def _scalarmult(P, e: int):
    # Iterative double-and-add (the reference is recursive; this avoids any
    # recursion-limit risk and is clearer).
    Q = [0, 1]  # identity
    while e > 0:
        if e & 1:
            Q = _edwards(Q, P)
        P = _edwards(P, P)
        e >>= 1
    return Q


def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1


def _encodeint(y: int) -> bytes:
    return y.to_bytes(b // 8, "little")


def _encodepoint(P) -> bytes:
    x, y = P
    val = (y & ((1 << (b - 1)) - 1)) | ((x & 1) << (b - 1))
    return val.to_bytes(b // 8, "little")


def _decodeint(s: bytes) -> int:
    return int.from_bytes(s, "little")


def _isoncurve(P) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - d * x * x * y * y) % q == 0


def _decodepoint(s: bytes):
    y = int.from_bytes(s, "little") & ((1 << (b - 1)) - 1)
    x = _xrecover(y)
    if x & 1 != _bit(s, b - 1):
        x = q - x
    P = [x, y]
    if not _isoncurve(P):
        raise ValueError("decoding point that is not on curve")
    return P


def _secret_scalar(h: bytes) -> int:
    a = 2 ** (b - 2)
    for i in range(3, b - 2):
        a += 2 ** i * _bit(h, i)
    return a


def _Hint(m: bytes) -> int:
    h = _H(m)
    return sum(2 ** i * _bit(h, i) for i in range(2 * b))


# ---- public API --------------------------------------------------------------


def publickey(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a 32-byte seed (private key)."""
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = _H(seed)
    a = _secret_scalar(h)
    A = _scalarmult(B, a)
    return _encodepoint(A)


def sign(msg: bytes, seed: bytes, pub: bytes) -> bytes:
    """Return the 64-byte Ed25519 signature of `msg` under `seed`.

    `pub` must be publickey(seed) (pass it in so callers don't recompute it).
    Used only by the build-time signer; the shipped app never calls this.
    """
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    h = _H(seed)
    a = _secret_scalar(h)
    r = _Hint(h[b // 8:b // 4] + msg)
    R = _scalarmult(B, r)
    S = (r + _Hint(_encodepoint(R) + pub + msg) * a) % l
    return _encodepoint(R) + _encodeint(S)


def verify(signature: bytes, msg: bytes, pub: bytes) -> bool:
    """Return True iff `signature` is a valid Ed25519 signature of `msg` under
    the 32-byte public key `pub`. NEVER raises -- returns False on any problem
    (wrong length, malformed point, bad signature). This is the ONLY function
    the shipped dashboard app calls."""
    try:
        if len(signature) != 64 or len(pub) != 32:
            return False
        R = _decodepoint(signature[:32])
        A = _decodepoint(pub)
        S = _decodeint(signature[32:])
        if S >= l:  # reject non-canonical S (malleability guard)
            return False
        h = _Hint(signature[:32] + pub + msg)
        # cofactorless check: [S]B == R + [h]A
        return _scalarmult(B, S) == _edwards(R, _scalarmult(A, h))
    except Exception:  # noqa: BLE001 -- verify must be total; any error => invalid
        return False
