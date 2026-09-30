"""One customer must never be able to read another customer's data.

Run against a real Postgres server, because this is the guarantee that makes sharing one
server acceptable and it cannot be established against a fake. If these tests are skipped,
the shared-server decision is unproven.

The important design point is the last test. A role with no privileges obviously cannot read
anything, so a test that only checked a fresh role would pass whatever the grants were. Each
crossing attempt here is made by a role that has already been granted everything it
legitimately needs inside its own database.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

import pytest

REPO: Final = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from deploy.installations.manifest import Installation  # noqa: E402
from deploy.installations.provision import lock_down_public_schema, provision  # noqa: E402

psycopg: Final = pytest.importorskip("psycopg", reason="the isolation guarantee needs a real Postgres server")


def _admin_url() -> str:
    """The server to prove isolation against, from the environment rather than from this file.

    No credential belongs in the repository, and a hardcoded one would also pin these tests to
    one developer's machine.
    """
    from os import environ

    url: Final = environ.get("DATABASE_URL")
    if not url:
        pytest.skip("set DATABASE_URL to a Postgres superuser to prove installation isolation")
    return url


def _host_port(url: str) -> tuple[str, int]:
    from urllib.parse import urlsplit

    parts: Final = urlsplit(url)
    return (parts.hostname or "127.0.0.1", parts.port or 5432)


def _pointed_at(url: str, database: str) -> str:
    """The same credentials, aimed at a different database.

    Built by replacing the path rather than by substituting the name in the whole string: the
    role is named after the database, so a plain replace changes the username too and the
    server then refuses the connection for a wrong password. That looks exactly like isolation
    working and proves nothing, which is what mutating the grants revealed.
    """
    from urllib.parse import urlsplit, urlunsplit

    parts: Final = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


FIRST: Final = Installation(key="isotest_one", hostname="one.tokeniq.test", version="v1.0.0")
SECOND: Final = Installation(key="isotest_two", hostname="two.tokeniq.test", version="v1.0.0")


def _admin():
    try:
        return psycopg.connect(_admin_url(), autocommit=True)
    except Exception as exc:  # noqa: BLE001  # any connection failure means the same thing here
        pytest.skip(f"no Postgres server to prove isolation against: {exc}")


def _drop(admin, installation: Installation) -> None:
    with admin.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{installation.database}" WITH (FORCE)')
        cur.execute(f'DROP ROLE IF EXISTS "{installation.role}"')


@pytest.fixture
def two_customers():
    """Two provisioned customers on one server, each with a table and a row of their own."""
    admin: Final = _admin()
    for installation in (FIRST, SECOND):
        _drop(admin, installation)

    urls: Final = {}
    for installation in (FIRST, SECOND):
        host, port = _host_port(_admin_url())
        result = provision(admin, installation, host=host, port=port)
        urls[installation.key] = result.database_url
        owner = psycopg.connect(result.database_url, autocommit=True)
        try:
            lock_down_public_schema(owner, installation)
            with owner.cursor() as cur:
                cur.execute("CREATE TABLE spend (amount text)")
                cur.execute("INSERT INTO spend (amount) VALUES (%s)", (f"secret-{installation.key}",))
        finally:
            owner.close()

    yield urls

    for installation in (FIRST, SECOND):
        _drop(admin, installation)
    admin.close()


def test_each_customer_can_read_its_own_data(two_customers) -> None:
    """The control. Without this the isolation tests below could pass because nothing works."""
    for key in (FIRST.key, SECOND.key):
        connection = psycopg.connect(two_customers[key], autocommit=True)
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT amount FROM spend")
                assert cur.fetchone()[0] == f"secret-{key}"
        finally:
            connection.close()


def test_one_customer_cannot_connect_to_the_other_customers_database(two_customers) -> None:
    """The line that matters. Owning your own database keeps nobody out of anyone else's;
    revoking CONNECT from PUBLIC is what does."""
    crossed: Final = _pointed_at(two_customers[FIRST.key], SECOND.database)

    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(crossed, autocommit=True).close()


def test_one_customer_cannot_read_the_other_customers_table_through_a_cross_database_reference(
    two_customers,
) -> None:
    """Postgres has no cross-database query, so this should fail on the reference itself.
    Asserted rather than assumed, because the whole decision rests on it."""
    connection: Final = psycopg.connect(two_customers[FIRST.key], autocommit=True)
    try:
        with connection.cursor() as cur, pytest.raises(psycopg.Error):
            cur.execute(f'SELECT * FROM "{SECOND.database}".public.spend')
    finally:
        connection.close()


def test_a_customer_with_every_privilege_it_legitimately_needs_still_cannot_cross(two_customers) -> None:
    """The test that makes the others meaningful.

    A role with no privileges cannot read anything, so a suite that only checked a fresh role
    would pass no matter how the grants were written. Here the first customer is given
    everything it could want inside its own database first, and must still be refused next
    door.
    """
    owner: Final = psycopg.connect(two_customers[FIRST.key], autocommit=True)
    try:
        with owner.cursor() as cur:
            cur.execute(f'GRANT ALL ON ALL TABLES IN SCHEMA public TO "{FIRST.role}"')
            cur.execute(f'GRANT ALL ON SCHEMA public TO "{FIRST.role}"')
            cur.execute("SELECT amount FROM spend")
            assert cur.fetchone() is not None
    finally:
        owner.close()

    crossed: Final = _pointed_at(two_customers[FIRST.key], SECOND.database)
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(crossed, autocommit=True).close()


def test_provisioning_the_same_customer_twice_does_not_reset_its_password(two_customers) -> None:
    """A second run must not take a live customer offline by rotating the password its
    running installation is already using."""
    admin: Final = _admin()
    try:
        host, port = _host_port(_admin_url())
        again = provision(admin, FIRST, host=host, port=port)
        assert again.created is False
        assert again.database_url == ""

        still_works = psycopg.connect(two_customers[FIRST.key], autocommit=True)
        still_works.close()
    finally:
        admin.close()


def test_a_role_that_somehow_gets_connect_still_cannot_see_into_the_schema(two_customers) -> None:
    """What locking down the public schema is actually for.

    Revoking CONNECT is the boundary. This is the layer behind it, for the day a role is
    granted CONNECT by mistake or by a future shared reader: without USAGE on the schema it
    cannot resolve a name there, so it is refused before table privileges are even consulted.

    Asserted on which refusal, not merely that one happened. "Permission denied for table"
    would mean the intruder could see into the schema and was stopped one layer later, which
    is a weaker position than the one this claims.
    """
    admin: Final = _admin()
    intruder_role: Final = "isotest_intruder"
    password: Final = "not-a-real-password-just-for-this-test"
    try:
        with admin.cursor() as cur:
            cur.execute(f'DROP ROLE IF EXISTS "{intruder_role}"')
            cur.execute(f"CREATE ROLE \"{intruder_role}\" WITH LOGIN PASSWORD '{password}'")
            cur.execute(f'GRANT CONNECT ON DATABASE "{FIRST.database}" TO "{intruder_role}"')

        host, port = _host_port(_admin_url())
        intruder_url = f"postgresql://{intruder_role}:{password}@{host}:{port}/{FIRST.database}"
        connection = psycopg.connect(intruder_url, autocommit=True)
        try:
            with connection.cursor() as cur, pytest.raises(psycopg.errors.InsufficientPrivilege) as refusal:
                cur.execute("SELECT amount FROM public.spend")
            assert "schema" in str(refusal.value).lower()
        finally:
            connection.close()
    finally:
        with admin.cursor() as cur:
            cur.execute(f'REVOKE ALL ON DATABASE "{FIRST.database}" FROM "{intruder_role}"')
            cur.execute(f'DROP ROLE IF EXISTS "{intruder_role}"')
        admin.close()
