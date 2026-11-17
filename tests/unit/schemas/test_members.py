"""Unit tests for the Member Pydantic schemas and every declared rule.

Schemas are pure Python, so these tests construct models directly: no
FastAPI app, no HTTP, and no database.
"""

import pytest
from pydantic import ValidationError

from app.models.member import Member
from app.schemas.members import MemberCreate, MemberResponse, MemberUpdate
from tests.helpers import member_payload

# MemberCreate and MemberUpdate share MemberBase, so every request rule is
# checked against both to prove neither one drifts from the other.
REQUEST_SCHEMAS = [MemberCreate, MemberUpdate]


@pytest.fixture(params=REQUEST_SCHEMAS, ids=lambda schema: schema.__name__)
def schema(request: pytest.FixtureRequest) -> type[MemberCreate] | type[MemberUpdate]:
    return request.param


# REQUIRED AND UNKNOWN FIELDS


@pytest.mark.parametrize("missing_field", ["name", "email", "membership_id", "phone"])
def test_member_request_requires_each_field(schema, missing_field: str) -> None:
    data = member_payload()
    data.pop(missing_field)

    with pytest.raises(ValidationError) as error:
        schema(**data)

    assert error.value.errors()[0]["type"] == "missing"
    assert error.value.errors()[0]["loc"] == (missing_field,)


@pytest.mark.parametrize("unknown_field", ["id", "nickname"])
def test_member_request_rejects_unknown_fields(schema, unknown_field: str) -> None:
    """extra="forbid" rejects undocumented fields, including a client-sent id."""
    with pytest.raises(ValidationError) as error:
        schema(**member_payload(**{unknown_field: 1}))

    assert error.value.errors()[0]["type"] == "extra_forbidden"


# NAME AND MEMBERSHIP ID LENGTHS


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("name", "   "),  # Becomes "" after trimming, then fails min_length.
        ("name", "n" * 121),
        ("membership_id", "   "),
        ("membership_id", "M" * 21),
    ],
    ids=["empty-name", "blank-name", "name-too-long", "blank-membership-id", "membership-id-too-long"],
)
def test_member_request_rejects_out_of_range_lengths(schema, field: str, value: str) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**member_payload(**{field: value}))

    assert error.value.errors()[0]["loc"] == (field,)


def test_member_request_accepts_inclusive_length_limits(schema) -> None:
    member = schema(**member_payload(name="n" * 120, membership_id="M" * 20))

    assert len(member.name) == 120
    assert len(member.membership_id) == 20


def test_member_request_trims_whitespace_before_checking_length(schema) -> None:
    """121 characters with padding is valid once trimmed to 120."""
    member = schema(**member_payload(name=f"  {'n' * 120}  ", membership_id="  LIB-0002  "))

    assert member.name == "n" * 120
    assert member.membership_id == "LIB-0002"


# EMAIL


@pytest.mark.parametrize("email", ["not-an-email", "ada@", "@example.com", "ada example@example.com"])
def test_member_request_rejects_invalid_email(schema, email: str) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**member_payload(email=email))

    assert error.value.errors()[0]["loc"] == ("email",)


def test_member_request_stores_email_in_lowercase(schema) -> None:
    """Lowercasing makes the uniqueness check case-insensitive."""
    member = schema(**member_payload(email="Ada.Lovelace@Example.COM"))

    assert member.email == "ada.lovelace@example.com"


# PHONE (documented rule: XXX-XXX-XXXX)


@pytest.mark.parametrize(
    "phone",
    ["5551234567", "555-1234-567", "(555) 123-4567", "555-123-456", "555-123-45678", "abc-def-ghij"],
)
def test_member_request_rejects_phone_outside_documented_format(schema, phone: str) -> None:
    with pytest.raises(ValidationError) as error:
        schema(**member_payload(phone=phone))

    assert error.value.errors()[0]["type"] == "string_pattern_mismatch"


def test_member_request_accepts_documented_phone_format(schema) -> None:
    assert schema(**member_payload(phone="972-555-0100")).phone == "972-555-0100"


# RESPONSE SCHEMA


def test_member_response_reads_an_orm_member() -> None:
    """from_attributes lets routes return SQLAlchemy objects directly."""
    source = Member(id=7, **member_payload())

    response = MemberResponse.model_validate(source)

    assert response.model_dump() == {"id": 7, **member_payload()}


def test_member_response_requires_positive_id() -> None:
    with pytest.raises(ValidationError):
        MemberResponse(id=0, **member_payload())
