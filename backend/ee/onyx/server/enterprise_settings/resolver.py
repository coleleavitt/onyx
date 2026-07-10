from ee.onyx.server.enterprise_settings.models import BrandAppearanceSettings
from ee.onyx.server.enterprise_settings.models import BrandProfile
from ee.onyx.server.enterprise_settings.models import EnterpriseSettings
from ee.onyx.server.enterprise_settings.models import normalize_brand_hostname
from ee.onyx.server.enterprise_settings.models import ResolvedEnterpriseSettings


def find_brand_profile(
    settings: EnterpriseSettings, hostname: str | None
) -> BrandProfile | None:
    normalized_hostname: str | None = None
    if hostname:
        try:
            normalized_hostname = normalize_brand_hostname(hostname)
        except ValueError:
            normalized_hostname = None

    if normalized_hostname:
        for profile in settings.brand_profiles:
            if normalized_hostname in profile.hostnames:
                return profile

    if settings.default_brand_id:
        for profile in settings.brand_profiles:
            if profile.id == settings.default_brand_id:
                return profile
    return None


def resolve_settings_for_hostname(
    settings: EnterpriseSettings, hostname: str | None
) -> ResolvedEnterpriseSettings:
    normalized_hostname: str | None = None
    if hostname:
        try:
            normalized_hostname = normalize_brand_hostname(hostname)
        except ValueError:
            normalized_hostname = None

    profile = find_brand_profile(settings, normalized_hostname)
    if profile:
        appearance = BrandAppearanceSettings.model_validate(
            profile.model_dump(exclude={"id", "name", "hostnames"})
        )
        return ResolvedEnterpriseSettings(
            **appearance.model_dump(),
            brand_id=profile.id,
            brand_name=profile.name,
            resolved_hostname=normalized_hostname,
        )

    appearance = BrandAppearanceSettings.model_validate(
        settings.model_dump(exclude={"brand_profiles", "default_brand_id"})
    )
    return ResolvedEnterpriseSettings(
        **appearance.model_dump(),
        resolved_hostname=normalized_hostname,
    )
