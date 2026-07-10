from ee.onyx.server.enterprise_settings.models import BrandAssetKind
from ee.onyx.server.enterprise_settings.store import get_brand_asset_filename
from ee.onyx.server.enterprise_settings.store import get_logotype_filename


def test_default_wordmark_preserves_legacy_logotype_file_id() -> None:
    assert get_brand_asset_filename(BrandAssetKind.WORDMARK) == "__logotype__"
    assert get_logotype_filename() == "__logotype__"


def test_profile_wordmark_uses_brand_specific_file_id() -> None:
    assert (
        get_brand_asset_filename(BrandAssetKind.WORDMARK, "Foundations")
        == "__brand_foundations_wordmark__"
    )
