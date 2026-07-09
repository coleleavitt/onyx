"""Settings overrides for complete-feature deployments."""

from ee.onyx.utils.tier import get_tier
from onyx.server.settings.models import Settings
from onyx.server.settings.models import Tier
from onyx.utils.variable_functionality import global_version
from shared_configs.configs import MULTI_TENANT


def apply_feature_availability_to_settings(settings: Settings) -> Settings:
    """Expose complete features and resolve the deployment's effective tier."""
    if MULTI_TENANT:
        settings.tier = get_tier()
    else:
        settings.tier = (
            Tier.ENTERPRISE if global_version.is_ee_version() else Tier.COMMUNITY
        )

    settings.ee_features_enabled = True
    return settings
