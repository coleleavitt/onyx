import os
from io import BytesIO
from typing import Any
from typing import cast
from typing import IO

from fastapi import UploadFile

from ee.onyx.server.enterprise_settings.models import AnalyticsScriptUpload
from ee.onyx.server.enterprise_settings.models import BrandAssetKind
from ee.onyx.server.enterprise_settings.models import EnterpriseSettings
from ee.onyx.server.enterprise_settings.models import normalize_brand_id
from onyx.configs.constants import FileOrigin
from onyx.configs.constants import KV_CUSTOM_ANALYTICS_SCRIPT_KEY
from onyx.configs.constants import KV_ENTERPRISE_SETTINGS_KEY
from onyx.configs.constants import ONYX_DEFAULT_APPLICATION_NAME
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_store.file_store import get_default_file_store
from onyx.key_value_store.factory import get_kv_store
from onyx.key_value_store.interface import KvKeyNotFoundError
from onyx.utils.logger import setup_logger

logger = setup_logger()

_LOGO_FILENAME = "__logo__"
_LOGOTYPE_FILENAME = "__logotype__"
_FAVICON_FILENAME = "__favicon__"
_DARK_LOGO_FILENAME = "__dark_logo__"
_DARK_WORDMARK_FILENAME = "__dark_wordmark__"


def load_settings() -> EnterpriseSettings:
    """Loads settings data directly from DB. This should be used primarily
    for checking what is actually in the DB, aka for editing and saving back settings.

    Runtime settings actually used by the application should be checked with
    load_runtime_settings as defaults may be applied at runtime.
    """

    dynamic_config_store = get_kv_store()
    try:
        settings = EnterpriseSettings(
            **cast(dict, dynamic_config_store.load(KV_ENTERPRISE_SETTINGS_KEY))
        )
    except KvKeyNotFoundError:
        settings = EnterpriseSettings()
        dynamic_config_store.store(KV_ENTERPRISE_SETTINGS_KEY, settings.model_dump())

    return settings


def store_settings(settings: EnterpriseSettings) -> None:
    """Stores settings directly to the kv store / db."""

    get_kv_store().store(KV_ENTERPRISE_SETTINGS_KEY, settings.model_dump())


def load_runtime_settings() -> EnterpriseSettings:
    """Loads settings from DB and applies any defaults or transformations for use
    at runtime.

    Should not be stored back to the DB.
    """
    enterprise_settings = load_settings()
    if not enterprise_settings.application_name:
        enterprise_settings.application_name = ONYX_DEFAULT_APPLICATION_NAME

    return enterprise_settings


_CUSTOM_ANALYTICS_SECRET_KEY = os.environ.get("CUSTOM_ANALYTICS_SECRET_KEY")


def load_analytics_script() -> str | None:
    dynamic_config_store = get_kv_store()
    try:
        return cast(str, dynamic_config_store.load(KV_CUSTOM_ANALYTICS_SCRIPT_KEY))
    except KvKeyNotFoundError:
        return None


def store_analytics_script(analytics_script_upload: AnalyticsScriptUpload) -> None:
    if (
        not _CUSTOM_ANALYTICS_SECRET_KEY
        or analytics_script_upload.secret_key != _CUSTOM_ANALYTICS_SECRET_KEY
    ):
        raise ValueError("Invalid secret key")

    get_kv_store().store(KV_CUSTOM_ANALYTICS_SCRIPT_KEY, analytics_script_upload.script)


def is_valid_file_type(filename: str) -> bool:
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".ico")
    return filename.lower().endswith(valid_extensions)


def guess_file_type(filename: str) -> str:
    if filename.lower().endswith(".png"):
        return "image/png"
    elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
        return "image/jpeg"
    elif filename.lower().endswith(".webp"):
        return "image/webp"
    elif filename.lower().endswith(".ico"):
        return "image/x-icon"
    return "application/octet-stream"


def get_brand_asset_filename(
    asset_kind: BrandAssetKind, brand_id: str | None = None
) -> str:
    if brand_id:
        normalized_brand_id = normalize_brand_id(brand_id)
        return f"__brand_{normalized_brand_id}_{asset_kind.value}__"

    default_filenames = {
        BrandAssetKind.LOGO: _LOGO_FILENAME,
        BrandAssetKind.DARK_LOGO: _DARK_LOGO_FILENAME,
        BrandAssetKind.FAVICON: _FAVICON_FILENAME,
        # Keep the original file id so existing single-brand logotypes remain valid.
        BrandAssetKind.WORDMARK: _LOGOTYPE_FILENAME,
        BrandAssetKind.DARK_WORDMARK: _DARK_WORDMARK_FILENAME,
    }
    return default_filenames[asset_kind]


def upload_brand_asset(
    file: UploadFile | str,
    asset_kind: BrandAssetKind,
    brand_id: str | None = None,
) -> bool:
    content: IO[Any]

    if isinstance(file, str):
        logger.notice("Uploading logo from local path %s", file)
        if not os.path.isfile(file) or not is_valid_file_type(file):
            logger.error("Invalid brand asset file type")
            return False

        with open(file, "rb") as file_handle:
            file_content = file_handle.read()
        content = BytesIO(file_content)
        display_name = file
        file_type = guess_file_type(file)

    else:
        logger.notice("Uploading logo from uploaded file")
        if not file.filename or not is_valid_file_type(file.filename):
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "Brand assets must be PNG, JPEG, WebP, or ICO files.",
            )
        content = file.file
        display_name = file.filename
        file_type = file.content_type or "image/jpeg"

    file_store = get_default_file_store()
    file_store.save_file(
        content=content,
        display_name=display_name,
        file_origin=FileOrigin.OTHER,
        file_type=file_type,
        file_id=get_brand_asset_filename(asset_kind, brand_id),
    )
    return True


def upload_logo(file: UploadFile | str, is_logotype: bool = False) -> bool:
    asset_kind = BrandAssetKind.WORDMARK if is_logotype else BrandAssetKind.LOGO
    return upload_brand_asset(file=file, asset_kind=asset_kind)


def get_logo_filename() -> str:
    return get_brand_asset_filename(BrandAssetKind.LOGO)


def get_logotype_filename() -> str:
    return get_brand_asset_filename(BrandAssetKind.WORDMARK)
