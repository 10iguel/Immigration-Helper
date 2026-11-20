"""Who is using the app."""
import re
from dataclasses import dataclass

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")  # a sanity check, not full RFC 5322
_MAX_EMAIL_LENGTH = 254


@dataclass(frozen=True)
class EmailAddress:
    """An email address, stored lowercase so "Ana@x.com" and "ana@x.com" are the same account."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > _MAX_EMAIL_LENGTH or not _EMAIL_PATTERN.match(normalized):
            raise ValueError("Enter a valid email address.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class User:
    user_id: int
    email: EmailAddress
