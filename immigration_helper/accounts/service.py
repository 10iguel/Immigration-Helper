"""Sign up, log in and log out. Login sessions are random tokens; only their SHA-256 hash is stored."""
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from immigration_helper.accounts.models import EmailAddress, User
from immigration_helper.accounts.passwords import check_password_rules, hash_password, verify_password

SESSION_LIFETIME = timedelta(days=14)


class EmailTakenError(Exception):
    pass


class InvalidCredentialsError(Exception):
    """Wrong email or password. Deliberately doesn't say which, so it can't reveal who has an account."""


@dataclass(frozen=True)
class LoginSession:
    token: str  # goes in the browser cookie; never stored
    user: User


class UserStore(Protocol):
    def add_user(self, email: EmailAddress, password_hash: str) -> User:
        """Raises EmailTakenError if the email already has an account."""

    def find_credentials(self, email: EmailAddress) -> tuple[User, str] | None:
        """The user and their password hash, or None."""

    def add_session(self, token_hash: str, user_id: int, expires_at: datetime) -> None: ...

    def user_for_session(self, token_hash: str, now: datetime) -> User | None:
        """The user of an unexpired session, or None."""

    def delete_session(self, token_hash: str) -> None: ...


class AccountService:
    def __init__(self, users: UserStore):
        self._users = users
        # Checked when the email is unknown, so a failed login takes the same time whether or not the account exists.
        self._dummy_hash = hash_password(secrets.token_urlsafe(16))

    def sign_up(self, email: EmailAddress, password: str) -> LoginSession:
        check_password_rules(password)
        user = self._users.add_user(email, hash_password(password))
        return self._start_session(user)

    def log_in(self, email: EmailAddress, password: str) -> LoginSession:
        found = self._users.find_credentials(email)
        if found is None:
            verify_password(password, self._dummy_hash)
            raise InvalidCredentialsError()
        user, password_hash = found
        if not verify_password(password, password_hash):
            raise InvalidCredentialsError()
        return self._start_session(user)

    def log_out(self, token: str) -> None:
        self._users.delete_session(_hash_token(token))

    def user_for(self, token: str) -> User | None:
        return self._users.user_for_session(_hash_token(token), datetime.now(timezone.utc))

    def _start_session(self, user: User) -> LoginSession:
        token = secrets.token_urlsafe(32)
        self._users.add_session(_hash_token(token), user.user_id, datetime.now(timezone.utc) + SESSION_LIFETIME)
        return LoginSession(token, user)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
