"""Unit tests for `ee.onyx.utils.tier`: complete-feature tier resolution
and the tier-requirement guards.
"""

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from onyx.db.enums import AccessType
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.settings.models import Tier


@patch("ee.onyx.utils.tier.MULTI_TENANT", False)
class TestSelfHostedTier:
    @patch("ee.onyx.utils.tier.global_version")
    def test_complete_build_is_enterprise(self, mock_global_version: MagicMock) -> None:
        from ee.onyx.utils.tier import get_tier

        mock_global_version.is_ee_version.return_value = True

        assert get_tier() == Tier.ENTERPRISE

    @patch("ee.onyx.utils.tier.global_version")
    def test_stripped_build_is_community(self, mock_global_version: MagicMock) -> None:
        from ee.onyx.utils.tier import get_tier

        mock_global_version.is_ee_version.return_value = False

        assert get_tier() == Tier.COMMUNITY


class TestRequireBusinessTierForSyncAccess:
    @pytest.mark.parametrize(
        "access_type",
        [AccessType.PUBLIC, AccessType.PRIVATE],
        ids=["public", "private"],
    )
    @patch("ee.onyx.utils.tier.get_tier")
    def test_non_sync_access_does_not_resolve_tier(
        self, mock_get_tier: MagicMock, access_type: AccessType
    ) -> None:
        from ee.onyx.utils.tier import require_business_tier_for_sync_access

        require_business_tier_for_sync_access(access_type)

        mock_get_tier.assert_not_called()

    @patch("ee.onyx.utils.tier.get_tier", return_value=Tier.COMMUNITY)
    def test_sync_at_community_is_rejected(self, _mock_get_tier: MagicMock) -> None:
        from ee.onyx.utils.tier import require_business_tier_for_sync_access

        with pytest.raises(OnyxError) as exc_info:
            require_business_tier_for_sync_access(AccessType.SYNC)

        assert exc_info.value.error_code == OnyxErrorCode.FEATURE_NOT_AVAILABLE

    @pytest.mark.parametrize("tier", [Tier.BUSINESS, Tier.ENTERPRISE])
    @patch("ee.onyx.utils.tier.get_tier")
    def test_sync_at_business_or_enterprise_is_allowed(
        self, mock_get_tier: MagicMock, tier: Tier
    ) -> None:
        from ee.onyx.utils.tier import require_business_tier_for_sync_access

        mock_get_tier.return_value = tier

        require_business_tier_for_sync_access(AccessType.SYNC)


class TestRequireBusinessTierForMultiSSO:
    """Below BUSINESS raises FEATURE_NOT_AVAILABLE. Enforcement-off passes
    without a tier read."""

    @patch("ee.onyx.utils.tier.LICENSE_ENFORCEMENT_ENABLED", True)
    @patch("ee.onyx.utils.tier.get_tier")
    def test_below_business_raises(self, mock_get_tier: MagicMock) -> None:
        from ee.onyx.utils.tier import require_business_tier_for_multi_sso

        mock_get_tier.return_value = Tier.COMMUNITY
        with pytest.raises(OnyxError) as exc_info:
            require_business_tier_for_multi_sso()
        assert exc_info.value.error_code == OnyxErrorCode.FEATURE_NOT_AVAILABLE

    @pytest.mark.parametrize(
        "tier",
        [Tier.BUSINESS, Tier.ENTERPRISE],
        ids=["business", "enterprise"],
    )
    @patch("ee.onyx.utils.tier.LICENSE_ENFORCEMENT_ENABLED", True)
    @patch("ee.onyx.utils.tier.get_tier")
    def test_business_or_above_passes(
        self, mock_get_tier: MagicMock, tier: Tier
    ) -> None:
        from ee.onyx.utils.tier import require_business_tier_for_multi_sso

        mock_get_tier.return_value = tier
        require_business_tier_for_multi_sso()

    @patch("ee.onyx.utils.tier.LICENSE_ENFORCEMENT_ENABLED", False)
    @patch("ee.onyx.utils.tier.get_tier")
    def test_enforcement_disabled_passes_without_tier_read(
        self, mock_get_tier: MagicMock
    ) -> None:
        from ee.onyx.utils.tier import require_business_tier_for_multi_sso

        require_business_tier_for_multi_sso()
        mock_get_tier.assert_not_called()
