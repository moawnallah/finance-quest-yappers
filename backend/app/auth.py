"""Email and password accounts.

Passwords are hashed with scrypt (Python standard library, OpenSSL): a random
16-byte salt per password, n=2**14, r=8, p=1, 32-byte key. Stored as
"scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>"; the plain password is never stored
or logged. Verification uses a constant-time comparison.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
from collections import defaultdict, deque

N, R, P, DKLEN = 2**14, 8, 1, 32
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "admin@crocoash.xyz,admin@crococash.xyz").split(",") if e.strip()}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def valid_email(email: str) -> bool:
    return len(email) <= 254 and bool(EMAIL_RE.match(email))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P, dklen=DKLEN, maxmem=64 * 1024 * 1024)
    b64 = lambda b: base64.b64encode(b).decode()
    return f"scrypt${N}${R}${P}${b64(salt)}${b64(key)}"


def verify_password(password: str, stored: str | None) -> bool:
    try:
        algo, n, r, p, salt, key = (stored or "").split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(key)
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(expected), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(got, expected)
    except (ValueError, TypeError):
        return False


# Simple brute-force brake: at most 5 failed logins per email per 5 minutes (per server process).
_failures: dict[str, deque] = defaultdict(deque)


def too_many_failures(email: str) -> bool:
    q = _failures[email]
    while q and q[0] < time.monotonic() - 300:
        q.popleft()
    return len(q) >= 5


def record_failure(email: str) -> None:
    _failures[email].append(time.monotonic())
