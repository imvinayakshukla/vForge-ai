"""Authentication: API-key middleware (OAuth2 can be added as a new checker)."""

from vforge.auth.middleware import ApiKeyMiddleware

__all__ = ["ApiKeyMiddleware"]
