"""Connections to PostgreSQL. Every SQL statement in the project lives in this package."""
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg import sql
from psycopg.rows import dict_row


class Database:
    """Opens one connection per unit of work, so each ``with database.connect()`` block is one transaction:
    it commits when the block ends normally and rolls back if it raises.

    ``schema`` puts the tables in another PostgreSQL schema, which the tests use to stay isolated.
    """

    def __init__(self, url: str, schema: str | None = None):
        self._url = url
        self._schema = schema

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self._url, row_factory=dict_row) as connection:
            if self._schema:
                connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self._schema)))
            yield connection
