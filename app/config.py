"""Validated application settings and configuration values."""

from enum import StrEnum

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageBackend(StrEnum):
    """Persistence implementations supported by the application."""

    DATABASE = "database"
    MEMORY = "memory"


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables and .env."""

    # No credential default lives in source code; DATABASE_URL must come from
    # the environment or .env when the database backend is selected.
    database_url: str | None = None
    database_echo_sql: bool = False
    storage_backend: StorageBackend = StorageBackend.DATABASE

    # Classroom Bearer tokens for the two predefined request roles. Like
    # DATABASE_URL, they have no default in source code: anyone who can read
    # the repository could otherwise authenticate as an administrator.
    # .env.example documents safe demonstration values.
    demo_member_token: str = Field(min_length=1)
    demo_admin_token: str = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def require_database_url_for_database_backend(self) -> "Settings":
        """Require database credentials only when PostgreSQL is selected."""
        if self.storage_backend is StorageBackend.DATABASE and not self.database_url:
            raise ValueError("DATABASE_URL is required when STORAGE_BACKEND=database")
        return self

    @model_validator(mode="after")
    def require_distinct_role_tokens(self) -> "Settings":
        """Refuse one token for both roles, which would make every caller an admin."""
        if self.demo_member_token == self.demo_admin_token:
            raise ValueError("DEMO_MEMBER_TOKEN and DEMO_ADMIN_TOKEN must be different")
        return self
