import re
from enum import Enum
from typing import Any
from typing import List
from urllib.parse import urlparse
from urllib.parse import urlsplit

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

_BRAND_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class NavigationItem(BaseModel):
    link: str
    title: str
    # Right now must be one of the FA icons
    icon: str | None = None
    # NOTE: SVG must not have a width / height specified
    # This is the actual SVG as a string. Done this way to reduce
    # complexity / having to store additional "logos" in Postgres
    svg_logo: str | None = None

    @classmethod
    def model_validate(cls, *args: Any, **kwargs: Any) -> "NavigationItem":
        instance = super().model_validate(*args, **kwargs)
        if bool(instance.icon) == bool(instance.svg_logo):
            raise ValueError("Exactly one of fa_icon or svg_logo must be specified")
        return instance


class LogoDisplayStyle(str, Enum):
    LOGO_AND_NAME = "logo_and_name"
    LOGO_ONLY = "logo_only"
    NAME_ONLY = "name_only"


class BrandAssetKind(str, Enum):
    LOGO = "logo"
    DARK_LOGO = "dark_logo"
    FAVICON = "favicon"
    WORDMARK = "wordmark"
    DARK_WORDMARK = "dark_wordmark"


def normalize_brand_id(value: str) -> str:
    normalized = value.strip().lower()
    if not _BRAND_ID_PATTERN.fullmatch(normalized):
        raise ValueError(
            "brand id must start with a letter or number and contain only "
            "lowercase letters, numbers, underscores, or hyphens"
        )
    return normalized


def normalize_brand_hostname(value: str) -> str:
    """Return a canonical hostname without a scheme, path, port, or trailing dot."""

    candidate = value.split(",", 1)[0].strip()
    if not candidate:
        raise ValueError("hostname cannot be empty")

    parsed = urlsplit(candidate if "://" in candidate else f"//{candidate}")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("hostname must not include a path, query, or fragment")
    if not parsed.hostname:
        raise ValueError("hostname is invalid")

    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname:
        raise ValueError("hostname cannot be empty")
    return hostname


class BrandAppearanceSettings(BaseModel):
    """Appearance values shared by the default brand and hostname profiles.

    NOTE: don't put anything sensitive in here, as this is accessible without auth."""

    application_name: str | None = None
    use_custom_logo: bool = False
    use_custom_dark_logo: bool = False
    use_custom_favicon: bool = False
    use_custom_wordmark: bool = False
    use_custom_dark_wordmark: bool = False
    use_custom_logotype: bool = False
    logo_display_style: LogoDisplayStyle | None = None
    accent_color: str | None = None
    login_background_color: str | None = None
    login_background_url: str | None = None
    login_subtitle: str | None = None

    # custom navigation
    custom_nav_items: List[NavigationItem] = Field(default_factory=list)

    # custom Chat components
    two_lines_for_chat_header: bool | None = None
    custom_lower_disclaimer_content: str | None = None
    custom_header_content: str | None = None
    custom_popup_header: str | None = None
    custom_popup_content: str | None = None
    enable_consent_screen: bool | None = None
    consent_screen_prompt: str | None = None
    show_first_visit_notice: bool | None = None
    custom_greeting_message: str | None = None

    # custom help link surfaced in the profile dropdown alongside the
    # built-in "Help & FAQ" item
    custom_help_link_url: str | None = None
    custom_help_link_label: str | None = None

    # hide the "Powered by Onyx" tagline under the sidebar logo
    hide_onyx_branding: bool | None = None

    @field_validator("accent_color", "login_background_color")
    @classmethod
    def _validate_hex_color(cls, value: str | None) -> str | None:
        if not value:
            return None
        if not _HEX_COLOR_PATTERN.fullmatch(value):
            raise ValueError("color must use the #RRGGBB format")
        return value.lower()

    @field_validator("login_background_url")
    @classmethod
    def _validate_background_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        if value.startswith("/") and not value.startswith("//"):
            return value
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "login_background_url must be root-relative or an absolute http(s) URL"
            )
        return value

    @field_validator("custom_help_link_url")
    @classmethod
    def _validate_help_link_scheme(cls, v: str | None) -> str | None:
        if not v:
            return v
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(
                "custom_help_link_url must be an absolute http or https URL"
            )
        return v

    def check_validity(self) -> None:
        return


class BrandProfile(BrandAppearanceSettings):
    id: str
    name: str
    hostnames: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return normalize_brand_id(value)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("brand name cannot be empty")
        if len(normalized) > 50:
            raise ValueError("brand name cannot exceed 50 characters")
        return normalized

    @field_validator("hostnames")
    @classmethod
    def _normalize_hostnames(cls, values: list[str]) -> list[str]:
        normalized = [normalize_brand_hostname(value) for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("brand hostnames must be unique")
        return normalized


class EnterpriseSettings(BrandAppearanceSettings):
    """Stored white-label settings and optional hostname-specific profiles."""

    brand_profiles: list[BrandProfile] = Field(default_factory=list)
    default_brand_id: str | None = None

    @model_validator(mode="after")
    def _validate_brand_profiles(self) -> "EnterpriseSettings":
        brand_ids = [profile.id for profile in self.brand_profiles]
        if len(brand_ids) != len(set(brand_ids)):
            raise ValueError("brand ids must be unique")

        hostnames = [
            hostname
            for profile in self.brand_profiles
            for hostname in profile.hostnames
        ]
        if len(hostnames) != len(set(hostnames)):
            raise ValueError("a hostname can only be assigned to one brand")

        if self.default_brand_id and self.default_brand_id not in set(brand_ids):
            raise ValueError("default_brand_id must reference an existing brand")
        return self


class ResolvedEnterpriseSettings(BrandAppearanceSettings):
    brand_id: str | None = None
    brand_name: str | None = None
    resolved_hostname: str | None = None


class AnalyticsScriptUpload(BaseModel):
    script: str
    secret_key: str
