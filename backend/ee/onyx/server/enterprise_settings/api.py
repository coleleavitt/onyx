from datetime import datetime
from datetime import timezone
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi import UploadFile
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy.orm import Session

from ee.onyx.db.scim import ScimDAL
from ee.onyx.server.enterprise_settings.models import AnalyticsScriptUpload
from ee.onyx.server.enterprise_settings.models import BrandAssetKind
from ee.onyx.server.enterprise_settings.models import EnterpriseSettings
from ee.onyx.server.enterprise_settings.models import ResolvedEnterpriseSettings
from ee.onyx.server.enterprise_settings.resolver import resolve_settings_for_hostname
from ee.onyx.server.enterprise_settings.store import get_brand_asset_filename
from ee.onyx.server.enterprise_settings.store import load_analytics_script
from ee.onyx.server.enterprise_settings.store import load_settings
from ee.onyx.server.enterprise_settings.store import store_analytics_script
from ee.onyx.server.enterprise_settings.store import store_settings
from ee.onyx.server.enterprise_settings.store import upload_brand_asset
from ee.onyx.server.scim.auth import generate_scim_token
from ee.onyx.server.scim.models import ScimTokenCreate
from ee.onyx.server.scim.models import ScimTokenCreatedResponse
from ee.onyx.server.scim.models import ScimTokenResponse
from ee.onyx.utils.tier import get_tier
from onyx.auth.permissions import require_permission
from onyx.auth.users import current_user_with_expired_token
from onyx.auth.users import get_user_manager
from onyx.auth.users import UserManager
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_store.file_store import get_default_file_store
from onyx.server.settings.models import Tier
from onyx.server.settings.tier_order import tier_at_least
from onyx.server.utils import BasicAuthenticationError
from onyx.utils.logger import setup_logger
from shared_configs.configs import MULTI_TENANT
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA
from shared_configs.contextvars import get_current_tenant_id

admin_router = APIRouter(prefix="/admin/enterprise-settings")
basic_router = APIRouter(prefix="/enterprise-settings")

logger = setup_logger()


class RefreshTokenData(BaseModel):
    access_token: str
    refresh_token: str
    session: dict = Field(..., description="Contains session information")
    userinfo: dict = Field(..., description="Contains user information")

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if "exp" not in self.session:
            raise ValueError("'exp' must be set in the session dictionary")
        if "userId" not in self.userinfo or "email" not in self.userinfo:
            raise ValueError(
                "'userId' and 'email' must be set in the userinfo dictionary"
            )


@basic_router.post("/refresh-token")
async def refresh_access_token(
    refresh_token: RefreshTokenData,
    user: User = Depends(current_user_with_expired_token),
    user_manager: UserManager = Depends(get_user_manager),
) -> None:
    try:
        logger.debug("Received response from Meechum auth URL for user %s", user.id)

        # Extract new tokens
        new_access_token = refresh_token.access_token
        new_refresh_token = refresh_token.refresh_token

        new_expiry = datetime.fromtimestamp(
            refresh_token.session["exp"] / 1000, tz=timezone.utc
        )
        expires_at_timestamp = int(new_expiry.timestamp())

        logger.debug("Access token has been refreshed for user %s", user.id)

        await user_manager.oauth_callback(
            oauth_name="custom",
            access_token=new_access_token,
            account_id=refresh_token.userinfo["userId"],
            account_email=refresh_token.userinfo["email"],
            expires_at=expires_at_timestamp,
            refresh_token=new_refresh_token,
            associate_by_email=True,
        )

        logger.info("Successfully refreshed tokens for user %s", user.id)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            logger.warning("Full authentication required for user %s", user.id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Full authentication required",
            )
        logger.error(
            "HTTP error occurred while refreshing token for user %s: %s",
            user.id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token",
        )
    except Exception as e:
        logger.error(
            "Unexpected error occurred while refreshing token for user %s: %s",
            user.id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@admin_router.put("")
def admin_ee_put_settings(
    settings: EnterpriseSettings,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> None:
    # Custom help link and Onyx-branding toggle are Enterprise-only. Block
    # writes to those fields when tier < ENTERPRISE so the FE disabled state
    # cannot be bypassed by crafting a request. Uses FEATURE_NOT_AVAILABLE
    # (402) to match the tier_gate middleware shape.
    if not tier_at_least(get_tier(), Tier.ENTERPRISE):
        existing = load_settings()
        if (
            settings.custom_help_link_url != existing.custom_help_link_url
            or settings.custom_help_link_label != existing.custom_help_link_label
        ):
            raise OnyxError(
                OnyxErrorCode.FEATURE_NOT_AVAILABLE,
                "Custom help link requires the Enterprise plan.",
            )
        if settings.hide_onyx_branding != existing.hide_onyx_branding:
            raise OnyxError(
                OnyxErrorCode.FEATURE_NOT_AVAILABLE,
                "Hiding Onyx branding requires the Enterprise plan.",
            )

    store_settings(settings)


@admin_router.get("")
def admin_ee_fetch_settings(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> EnterpriseSettings:
    return load_settings()


def _get_request_hostname(request: Request) -> str | None:
    return request.headers.get("x-forwarded-host") or request.headers.get("host")


@basic_router.get("")
def ee_fetch_settings(request: Request) -> ResolvedEnterpriseSettings:
    if MULTI_TENANT:
        tenant_id = get_current_tenant_id()
        if not tenant_id or tenant_id == POSTGRES_DEFAULT_SCHEMA:
            raise BasicAuthenticationError(detail="User must authenticate")

    return resolve_settings_for_hostname(
        load_settings(), _get_request_hostname(request)
    )


@admin_router.put("/logo")
def put_logo(
    file: UploadFile,
    is_logotype: bool = False,
    brand_id: str | None = None,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> None:
    asset_kind = BrandAssetKind.WORDMARK if is_logotype else BrandAssetKind.LOGO
    _validate_brand_id_exists(brand_id)
    upload_brand_asset(file=file, asset_kind=asset_kind, brand_id=brand_id)


def _validate_brand_id_exists(brand_id: str | None) -> None:
    if brand_id is None:
        return
    if not any(profile.id == brand_id for profile in load_settings().brand_profiles):
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Brand profile not found")


@admin_router.put("/brand-assets/{asset_kind}")
def put_brand_asset(
    asset_kind: BrandAssetKind,
    file: UploadFile,
    brand_id: str | None = None,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> None:
    _validate_brand_id_exists(brand_id)
    upload_brand_asset(file=file, asset_kind=asset_kind, brand_id=brand_id)


def _fetch_brand_asset_by_id(
    asset_kind: BrandAssetKind,
    brand_id: str | None,
    db_session: Session,  # noqa: ARG001
) -> Response:
    filename = get_brand_asset_filename(asset_kind, brand_id)
    try:
        file_store = get_default_file_store()
        onyx_file = file_store.get_file_with_mime_type(filename)
        if not onyx_file:
            raise OnyxError(OnyxErrorCode.NOT_FOUND, "Brand asset not found")
    except OnyxError:
        raise
    except Exception:
        logger.exception("Failed to fetch brand asset %s", filename)
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Brand asset not found")
    else:
        return Response(
            content=onyx_file.data,
            media_type=onyx_file.mime_type,
            headers={"Cache-Control": "no-cache"},
        )


@admin_router.get("/brand-assets/{asset_kind}")
def admin_fetch_brand_asset(
    asset_kind: BrandAssetKind,
    brand_id: str | None = None,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> Response:
    _validate_brand_id_exists(brand_id)
    return _fetch_brand_asset_by_id(asset_kind, brand_id, db_session)


def fetch_brand_asset_helper(
    request: Request,
    asset_kind: BrandAssetKind,
    db_session: Session,
) -> Response:
    resolved = resolve_settings_for_hostname(
        load_settings(), _get_request_hostname(request)
    )
    return _fetch_brand_asset_by_id(asset_kind, resolved.brand_id, db_session)


@basic_router.get("/brand-assets/{asset_kind}")
def fetch_brand_asset(
    asset_kind: BrandAssetKind,
    request: Request,
    db_session: Session = Depends(get_session),
) -> Response:
    return fetch_brand_asset_helper(request, asset_kind, db_session)


@basic_router.get("/logotype")
def fetch_logotype(
    request: Request, db_session: Session = Depends(get_session)
) -> Response:
    return fetch_brand_asset_helper(request, BrandAssetKind.WORDMARK, db_session)


@basic_router.get("/logo")
def fetch_logo(
    request: Request,
    is_logotype: bool = False,
    db_session: Session = Depends(get_session),
) -> Response:
    asset_kind = BrandAssetKind.WORDMARK if is_logotype else BrandAssetKind.LOGO
    return fetch_brand_asset_helper(request, asset_kind, db_session)


@basic_router.get("/favicon")
def fetch_favicon(
    request: Request, db_session: Session = Depends(get_session)
) -> Response:
    return fetch_brand_asset_helper(request, BrandAssetKind.FAVICON, db_session)


@admin_router.put("/custom-analytics-script")
def upload_custom_analytics_script(
    script_upload: AnalyticsScriptUpload,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
) -> None:
    try:
        store_analytics_script(script_upload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@basic_router.get("/custom-analytics-script")
def fetch_custom_analytics_script() -> str | None:
    return load_analytics_script()


# ---------------------------------------------------------------------------
# SCIM token management
# ---------------------------------------------------------------------------


def _get_scim_dal(db_session: Session = Depends(get_session)) -> ScimDAL:
    return ScimDAL(db_session)


@admin_router.get("/scim/token")
def get_active_scim_token(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    dal: ScimDAL = Depends(_get_scim_dal),
) -> ScimTokenResponse | None:
    """Return the currently active SCIM token's metadata, or null if none."""
    token = dal.get_active_token()
    if not token:
        return None

    # Derive the IdP domain from the first synced user as a heuristic.
    idp_domain: str | None = None
    mappings, _total = dal.list_user_mappings(start_index=1, count=1)
    if mappings:
        user = dal.get_user(mappings[0].user_id)
        if user and "@" in user.email:
            idp_domain = user.email.rsplit("@", 1)[1]

    return ScimTokenResponse(
        id=token.id,
        name=token.name,
        token_display=token.token_display,
        is_active=token.is_active,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        idp_domain=idp_domain,
    )


@admin_router.post("/scim/token", status_code=201)
def create_scim_token(
    body: ScimTokenCreate,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    dal: ScimDAL = Depends(_get_scim_dal),
) -> ScimTokenCreatedResponse:
    """Create a new SCIM bearer token.

    Only one token is active at a time — creating a new token automatically
    revokes all previous tokens. The raw token value is returned exactly once
    in the response; it cannot be retrieved again.
    """
    raw_token, hashed_token, token_display = generate_scim_token()
    token = dal.create_token(
        name=body.name,
        hashed_token=hashed_token,
        token_display=token_display,
        created_by_id=user.id,
    )
    dal.commit()

    return ScimTokenCreatedResponse(
        id=token.id,
        name=token.name,
        token_display=token.token_display,
        is_active=token.is_active,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        raw_token=raw_token,
    )
