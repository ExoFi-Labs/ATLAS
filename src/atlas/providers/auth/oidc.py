from atlas.config import AuthSettings
from atlas.providers.base import UserContext


class OIDCAuthProvider:
    """
    SSO stub for Azure AD / Okta migration.

    Wire up authlib or python-jose token validation here when deploying to work.
    The rest of ATLAS only depends on UserContext (user_id, roles, groups).
    """

    def __init__(self, settings: AuthSettings) -> None:
        self.settings = settings
        if not settings.oidc_issuer or not settings.oidc_client_id:
            raise ValueError(
                "OIDC auth selected but ATLAS_AUTH__OIDC_ISSUER / CLIENT_ID are not configured"
            )

    async def authenticate(self, authorization: str | None) -> UserContext:
        if not authorization or not authorization.startswith("Bearer "):
            raise PermissionError("Missing bearer token")

        # TODO(work-migration): validate JWT against OIDC issuer JWKS and map claims → roles
        raise NotImplementedError(
            "OIDC authentication is not implemented yet. "
            "Use ATLAS_AUTH__PROVIDER=dev for local development."
        )

    async def get_login_url(self) -> str | None:
        # TODO(work-migration): return authorization URL for SSO redirect
        return None
