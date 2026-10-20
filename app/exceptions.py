"""Application outcomes raised by services without depending on FastAPI."""


class MemberNotFoundError(Exception):
    """Signal that the requested or referenced Member does not exist.

    These exceptions live outside the router package so services stay usable
    from HTTP routes, scripts, or background jobs without importing FastAPI.
    """


class BookNotFoundError(Exception):
    """Signal that the requested Book does not exist."""


class MemberHasBooksError(Exception):
    """Signal that a Member cannot be deleted while Books reference it."""


class MemberEmailAlreadyExistsError(Exception):
    """Signal that another Member already uses the requested email address."""


class MembershipIdAlreadyExistsError(Exception):
    """Signal that another Member already uses the requested membership ID."""


class IsbnAlreadyExistsError(Exception):
    """Signal that another Book already uses the requested ISBN."""
