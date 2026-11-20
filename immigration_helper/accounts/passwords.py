"""Password hashing with scrypt from the standard library: slow on purpose, salted, and never reversible."""
import hashlib
import hmac
import secrets

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 200

# scrypt cost settings (n = CPU/memory cost). Stored with each hash, so they can be raised later without
# breaking existing passwords.
_N, _R, _P = 2**14, 8, 1
_SALT_BYTES = 16


def check_password_rules(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(f"Use a password of {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters.")


def hash_password(password: str) -> str:
    """Returns "scrypt$n$r$p$salt$hash" (hex), safe to store in the database."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _scrypt(password, salt, _N, _R, _P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    algorithm, n, r, p, salt, expected = stored.split("$")
    if algorithm != "scrypt":
        raise ValueError(f"Unknown password hash algorithm: {algorithm!r}")
    digest = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    return hmac.compare_digest(digest.hex(), expected)  # constant time, so timing doesn't leak the hash


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p)
