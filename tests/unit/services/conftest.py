"""Test doubles for unit-testing the database services without PostgreSQL.

A database service only talks to two collaborators: the session factory and
the repositories. Replacing both with mocks isolates the service's decisions
(which checks run, which exception is raised, whether a write happens) from
SQLAlchemy and PostgreSQL. Integration tests cover the real collaborators.
"""

from collections.abc import Generator

import pytest
from mockito import args, mock, unstub, when

from tests.fakes import FakeDatabase


@pytest.fixture
def fake_database() -> Generator[FakeDatabase, None, None]:
    """Build a session factory whose two context forms yield one fake Session.

    The services use ``with factory() as session`` for reads and
    ``with factory.begin() as session`` for writes. A ``with`` statement calls
    ``__enter__`` and ``__exit__``, so both are stubbed. ``__exit__`` returns
    None (falsy), which lets an exception raised inside the block propagate
    exactly as SQLAlchemy's rollback-then-reraise would.
    """
    session = mock()
    factory = mock()
    read_context = mock()
    transaction_context = mock()

    when(read_context).__enter__().thenReturn(session)
    when(read_context).__exit__(*args)
    when(factory).__call__().thenReturn(read_context)

    when(transaction_context).__enter__().thenReturn(session)
    when(transaction_context).__exit__(*args)
    when(factory).begin().thenReturn(transaction_context)

    try:
        # mock() returns None for any call that is not stubbed, so a
        # repository lookup "finds nothing" unless a test says otherwise.
        yield FakeDatabase(factory, session, member_repository=mock(), book_repository=mock())
    finally:
        # Remove every stub, including patched module attributes.
        unstub()
