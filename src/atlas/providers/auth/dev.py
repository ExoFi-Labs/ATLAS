from atlas.config import AuthSettings
from atlas.providers.base import UserContext


class DevAuthProvider:
    """Local development auth — replace with OIDC at work via ATLAS_AUTH__PROVIDER=oidc."""

    def __init__(self, settings: AuthSettings) -> None:
        self.settings = settings

    async def authenticate(self, authorization: str | None) -> UserContext:
        roles = [role.strip() for role in self.settings.dev_roles.split(",") if role.strip()]
        return UserContext(user_id=self.settings.dev_user_id, roles=roles)

    async def get_login_url(self) -> str | None:
        return None
