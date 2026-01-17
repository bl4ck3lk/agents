"""Authentication backend configuration."""

from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from agents.api.auth.config import auth_config

# Bearer token transport
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    """Get JWT strategy for authentication."""
    return JWTStrategy(
        secret=auth_config.secret_key,
        lifetime_seconds=auth_config.access_token_expire_minutes * 60,
    )


# Main authentication backend
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)
