"""Tests for complete-feature settings resolution."""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from onyx.server.settings.models import ApplicationStatus
from onyx.server.settings.models import Settings
from onyx.server.settings.models import Tier


@pytest.fixture
def base_settings() -> Settings:
    return Settings(application_status=ApplicationStatus.ACTIVE)

@patch("ee.onyx.server.settings.api.MULTI_TENANT", False)
@patch("ee.onyx.server.settings.api.global_version")
def test_self_hosted_complete_build_is_enterprise(
    mock_global_version: MagicMock, base_settings: Settings
) -> None:
    from ee.onyx.server.settings.api import apply_feature_availability_to_settings

    mock_global_version.is_ee_version.return_value = True

    result = apply_feature_availability_to_settings(base_settings)

    assert result.application_status == ApplicationStatus.ACTIVE
    assert result.ee_features_enabled is True
    assert result.tier == Tier.ENTERPRISE


@pytest.mark.parametrize("tier", [Tier.BUSINESS, Tier.ENTERPRISE])
@patch("ee.onyx.server.settings.api.MULTI_TENANT", True)
@patch("ee.onyx.server.settings.api.get_tier")
def test_cloud_preserves_resolved_tenant_tier(
    mock_get_tier: MagicMock,
    tier: Tier,
    base_settings: Settings,
) -> None:
    from ee.onyx.server.settings.api import apply_feature_availability_to_settings

    mock_get_tier.return_value = tier

    result = apply_feature_availability_to_settings(base_settings)

    assert result.ee_features_enabled is True
    assert result.tier == tier
    mock_get_tier.assert_called_once_with()
