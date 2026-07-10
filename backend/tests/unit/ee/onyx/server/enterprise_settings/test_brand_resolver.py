import pytest
from pydantic import ValidationError

from ee.onyx.server.enterprise_settings.models import BrandProfile
from ee.onyx.server.enterprise_settings.models import EnterpriseSettings
from ee.onyx.server.enterprise_settings.models import normalize_brand_hostname
from ee.onyx.server.enterprise_settings.resolver import resolve_settings_for_hostname


def test_normalize_brand_hostname() -> None:
    assert (
        normalize_brand_hostname("https://Chat.FIWealth.com:443/")
        == "chat.fiwealth.com"
    )
    assert normalize_brand_hostname("MAGELLANFINANCIAL.COM.") == "magellanfinancial.com"


def test_duplicate_hostnames_across_profiles_are_rejected() -> None:
    with pytest.raises(ValidationError, match="only be assigned to one brand"):
        EnterpriseSettings(
            brand_profiles=[
                BrandProfile(
                    id="foundations",
                    name="Foundations",
                    hostnames=["chat.example.com"],
                ),
                BrandProfile(
                    id="magellan",
                    name="Magellan",
                    hostnames=["CHAT.EXAMPLE.COM"],
                ),
            ]
        )


def test_resolve_exact_hostname_profile() -> None:
    settings = EnterpriseSettings(
        application_name="Default AI",
        brand_profiles=[
            BrandProfile(
                id="foundations",
                name="Foundations",
                hostnames=["chat.fiwealth.com"],
                application_name="Foundations AI",
                accent_color="#E3530F",
            )
        ],
    )

    resolved = resolve_settings_for_hostname(settings, "chat.fiwealth.com:443")

    assert resolved.brand_id == "foundations"
    assert resolved.brand_name == "Foundations"
    assert resolved.application_name == "Foundations AI"
    assert resolved.accent_color == "#e3530f"
    assert resolved.resolved_hostname == "chat.fiwealth.com"


def test_unknown_hostname_uses_configured_default_profile() -> None:
    settings = EnterpriseSettings(
        application_name="Legacy Default",
        default_brand_id="magellan",
        brand_profiles=[
            BrandProfile(
                id="magellan",
                name="Magellan",
                hostnames=["chat.magellanfinancial.com"],
                application_name="Magellan AI",
            )
        ],
    )

    resolved = resolve_settings_for_hostname(settings, "localhost:3000")

    assert resolved.brand_id == "magellan"
    assert resolved.application_name == "Magellan AI"
    assert resolved.resolved_hostname == "localhost"


def test_unknown_hostname_uses_legacy_settings_without_default_profile() -> None:
    settings = EnterpriseSettings(application_name="Existing Onyx Name")

    resolved = resolve_settings_for_hostname(settings, "localhost:3000")

    assert resolved.brand_id is None
    assert resolved.application_name == "Existing Onyx Name"
