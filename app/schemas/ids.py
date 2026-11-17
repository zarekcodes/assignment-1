"""Identifier limits shared by request schemas and path parameters."""

# Primary and foreign keys are PostgreSQL INTEGER columns, which hold values
# up to 2**31 - 1. A larger ID can never match a row, and sending one to
# PostgreSQL fails with "integer out of range" (an unhandled 500). Declaring
# the limit in the contract rejects it with 422 before any service runs, so
# both storage backends behave the same and OpenAPI documents the range.
MAX_ID = 2_147_483_647
