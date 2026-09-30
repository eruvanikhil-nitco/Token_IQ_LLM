"""Create one customer's database and role on the shared Postgres server.

Sharing a server is what makes a small customer profitable, and it is also the one decision
that could expose one company's spend and provider credentials to another. The guarantee does
not rest on the application behaving: the product is a fork of a codebase with no tenant
boundary, which is the whole reason each customer gets an installation of their own.

It rests on the database. Each installation connects as a role that owns its own database and
is granted nothing anywhere else, and the public schema is locked down so a new role cannot
read or write in a database that is not its own. A connection string leaked from one
installation reaches that customer's data and nothing else.

Idempotent on purpose. Running it again on an existing customer changes nothing and never
resets a password, because resetting one takes a live customer offline.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Final, Protocol
from urllib.parse import quote

from psycopg import sql

from deploy.installations.manifest import Installation

PASSWORD_BYTES: Final = 32
"""256 bits. These are generated once and stored in Secrets Manager, never typed by a human,
so there is no reason for them to be short."""


class Cursor(Protocol):
    def execute(self, query: str, params: tuple[object, ...] | None = ...) -> object: ...

    def fetchone(self) -> tuple[object, ...] | None: ...


class Connection(Protocol):
    def cursor(self) -> object: ...


@dataclass(frozen=True, slots=True)
class Provisioned:
    """What a caller needs to finish creating the installation."""

    installation: Installation
    database_url: str
    created: bool
    """False when the customer already existed, so a caller can tell "made" from "was there"."""


def _exists(cursor: Cursor, query: str, name: str) -> bool:
    cursor.execute(query, (name,))
    return cursor.fetchone() is not None


def database_url_for(installation: Installation, *, host: str, port: int, password: str) -> str:
    """The connection string this installation uses, with the password safely encoded.

    A generated password can contain characters that mean something in a URL, and a naive
    join produces a string that either fails to parse or silently connects somewhere else.
    """
    return (
        f"postgresql://{quote(installation.role, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}/{quote(installation.database, safe='')}"
    )


def provision(
    connection: object,
    installation: Installation,
    *,
    host: str,
    port: int,
) -> Provisioned:
    """Create the customer's role and database if they are not already there.

    Identifiers and the password are composed with psycopg's own quoting, because Postgres
    accepts a bound parameter for neither: a placeholder in `CREATE ROLE ... PASSWORD` is a
    syntax error, which is the sort of thing only a real server tells you.
    """
    cursor: Final = connection.cursor()  # pyright: ignore[reportAttributeAccessIssue]  # Connection protocol
    role: Final = installation.role
    database: Final = installation.database

    role_existed: Final = _exists(cursor, "SELECT 1 FROM pg_roles WHERE rolname = %s", role)
    db_existed: Final = _exists(cursor, "SELECT 1 FROM pg_database WHERE datname = %s", database)

    if role_existed and db_existed:
        return Provisioned(installation=installation, database_url="", created=False)

    password: Final = secrets.token_urlsafe(PASSWORD_BYTES)

    # CREATE ROLE takes no bound parameter for the password: Postgres rejects a placeholder
    # there outright. Composed with psycopg's own quoting rather than an f-string, so the
    # password is escaped by the driver instead of by us guessing what the generator emits.
    if not role_existed:
        cursor.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
        )
    if not db_existed:
        cursor.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier(role)))

    # Nothing beyond its own database. REVOKE CONNECT from PUBLIC is the line that matters:
    # without it every role on the server can open every database, and owning your own would
    # not keep anybody out of anyone else's.
    cursor.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(database)))
    cursor.execute(
        sql.SQL("GRANT CONNECT, TEMPORARY ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role))
    )
    cursor.execute(sql.SQL("ALTER DATABASE {} OWNER TO {}").format(sql.Identifier(database), sql.Identifier(role)))

    return Provisioned(
        installation=installation,
        database_url=database_url_for(installation, host=host, port=port, password=password),
        created=True,
    )


def lock_down_public_schema(connection: object, installation: Installation) -> None:
    """Take the default public rights away inside the customer's own database.

    Postgres before 15 grants CREATE on the public schema to every role, and every version
    grants USAGE. Left alone, any role that got CONNECT could read this customer's tables.
    Runs connected to the customer's database rather than to the server's default one.
    """
    cursor: Final = connection.cursor()  # pyright: ignore[reportAttributeAccessIssue]  # Connection protocol
    cursor.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")

    # Redundant on Postgres 15 and later, where `public` is owned by `pg_database_owner` and
    # this role already has it. Kept for 13 and 14, where the revoke above would otherwise
    # take the customer's own rights away with everyone else's. No test kills this line on a
    # 15+ server, which is the honest reason it is called out rather than left looking covered.
    cursor.execute(sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(installation.role)))
