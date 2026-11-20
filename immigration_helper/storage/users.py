"""Accounts and login sessions in PostgreSQL."""
from datetime import datetime

from psycopg import errors

from immigration_helper.accounts import EmailAddress, EmailTakenError, User
from immigration_helper.storage.database import Database


class PostgresUserStore:
    def __init__(self, database: Database):
        self._database = database

    def add_user(self, email: EmailAddress, password_hash: str) -> User:
        try:
            with self._database.connect() as connection:
                row = connection.execute(
                    "INSERT INTO app_user (email, password_hash) VALUES (%s, %s) RETURNING user_id",
                    (email.value, password_hash),
                ).fetchone()
        except errors.UniqueViolation as error:
            raise EmailTakenError() from error
        return User(row["user_id"], email)

    def find_credentials(self, email: EmailAddress) -> tuple[User, str] | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT user_id, password_hash FROM app_user WHERE email = %s", (email.value,)
            ).fetchone()
        return (User(row["user_id"], email), row["password_hash"]) if row else None

    def add_session(self, token_hash: str, user_id: int, expires_at: datetime) -> None:
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO user_session (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (token_hash, user_id, expires_at),
            )

    def user_for_session(self, token_hash: str, now: datetime) -> User | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT u.user_id, u.email FROM user_session s JOIN app_user u ON u.user_id = s.user_id "
                "WHERE s.token_hash = %s AND s.expires_at > %s",
                (token_hash, now),
            ).fetchone()
        return User(row["user_id"], EmailAddress(row["email"])) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._database.connect() as connection:
            connection.execute("DELETE FROM user_session WHERE token_hash = %s", (token_hash,))
