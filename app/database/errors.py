"""Translate database constraint violations into application exceptions."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError


def violated_constraint(error: IntegrityError) -> str | None:
    """Return the name of the constraint PostgreSQL reported, if available."""
    diagnostics = getattr(error.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)


@contextmanager
def translate_integrity_errors(
    errors_by_constraint: Mapping[str, type[Exception]],
) -> Iterator[None]:
    """Raise the mapped application exception when a known constraint fails.

    Services check uniqueness and relationships before writing, but two
    concurrent requests can both pass those checks. The database constraint
    then rejects the second write, and this keeps raw driver details out of
    the API response. Unrecognized integrity errors are re-raised unchanged.
    """
    try:
        yield
    except IntegrityError as error:
        exception_type = errors_by_constraint.get(violated_constraint(error) or "")
        if exception_type is None:
            raise
        raise exception_type from error
