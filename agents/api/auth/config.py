"""Authentication configuration."""

import os
import secrets
from dataclasses import dataclass


@dataclass
class AuthConfig:
    """Configuration for authentication."""

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours
    refresh_token_expire_days: int = 30

    # OAuth providers
    google_client_id: str | None = None
    google_client_secret: str | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None

    # Email
    resend_api_key: str | None = None
    email_from: str = "noreply@agents.app"

    # Frontend URLs for redirects
    frontend_url: str = "http://localhost:3000"
    verify_email_url: str = "http://localhost:3000/auth/verify"
    reset_password_url: str = "http://localhost:3000/auth/reset-password"

    @classmethod
    def from_env(cls) -> AuthConfig:
        """Create config from environment variables."""
        return cls(
            secret_key=os.getenv("SECRET_KEY", secrets.token_urlsafe(32)),
            google_client_id=os.getenv("GOOGLE_CLIENT_ID"),
            google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            github_client_id=os.getenv("GITHUB_CLIENT_ID"),
            github_client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
            resend_api_key=os.getenv("RESEND_API_KEY"),
            email_from=os.getenv("EMAIL_FROM", "noreply@agents.app"),
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:3000"),
            verify_email_url=os.getenv("VERIFY_EMAIL_URL", "http://localhost:3000/auth/verify"),
            reset_password_url=os.getenv(
                "RESET_PASSWORD_URL", "http://localhost:3000/auth/reset-password"
            ),
        )


# Global config instance
auth_config = AuthConfig.from_env()
