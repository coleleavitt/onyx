"""Per-tenant tier resolution.

Cloud: Redis HGET → CP lazy-refresh on miss → BUSINESS fallback.
Self-hosted: ENTERPRISE whenever the complete implementation is loaded.

Promotion rule (cloud-only): a tenant whose contractual `customer_tier`
is BUSINESS but whose subscription is still inside its trial window
(`trial_end > now`) resolves to `Tier.ENTERPRISE` — they're being shown
a preview of the Enterprise feature set during the trial. The contractual
`customer_tier` on the tenant row is left unchanged; promotion is applied
purely at read time so the moment `trial_end` passes, the cached entry
naturally resolves back to BUSINESS without waiting on a webhook.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone

import requests
from redis.exceptions import RedisError

from ee.onyx.configs.app_configs import LICENSE_ENFORCEMENT_ENABLED
from ee.onyx.server.license.models import CustomerTier
from ee.onyx.server.tenants.billing import fetch_billing_information
from ee.onyx.server.tenants.models import BillingInformation
from ee.onyx.server.tenants.models import SubscriptionStatusResponse
from ee.onyx.server.tenants.tier_management import get_cached_tier
from ee.onyx.server.tenants.tier_management import update_tenant_tier
from onyx.db.enums import AccessType
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.settings.models import Tier
from onyx.server.settings.tier_order import tier_at_least
from onyx.utils.logger import setup_logger
from onyx.utils.variable_functionality import global_version
from shared_configs.configs import MULTI_TENANT
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()


_CUSTOMER_TIER_TO_TIER: dict[CustomerTier, Tier] = {
    CustomerTier.BUSINESS: Tier.BUSINESS,
    CustomerTier.ENTERPRISE: Tier.ENTERPRISE,
}


def _effective_tier(customer_tier: CustomerTier, trial_end: datetime | None) -> Tier:
    """Apply the cloud trial-business → enterprise promotion.

    A BUSINESS tenant whose `trial_end` is still in the future is resolved
    to ENTERPRISE for the duration of the trial. Once `trial_end` is in the
    past (or absent), the unpromoted mapping is used.
    """
    if (
        customer_tier == CustomerTier.BUSINESS
        and trial_end is not None
        and trial_end > datetime.now(timezone.utc)
    ):
        return Tier.ENTERPRISE
    # Unknown tier (e.g. a future CustomerTier value): fall back to the
    # cloud floor — BUSINESS — rather than over-granting ENTERPRISE.
    return _CUSTOMER_TIER_TO_TIER.get(customer_tier, Tier.BUSINESS)


def _self_hosted_tier() -> Tier:
    return Tier.ENTERPRISE if global_version.is_ee_version() else Tier.COMMUNITY


def _extract_billing_state(
    billing: BillingInformation | SubscriptionStatusResponse,
) -> tuple[CustomerTier, datetime | None] | None:
    customer_tier = getattr(billing, "customer_tier", None)
    if customer_tier is None:
        return None
    trial_end = getattr(billing, "trial_end", None)
    if not isinstance(trial_end, datetime):
        trial_end = None
    elif trial_end.tzinfo is None or trial_end.tzinfo.utcoffset(trial_end) is None:
        # Mirrors the cache-read guard: a naive trial_end would crash the
        # tz-aware comparison in `_effective_tier`. Drop it and log so a
        # CP-side regression is visible.
        logger.warning("CP returned naive trial_end; dropping: %r", trial_end)
        trial_end = None
    return customer_tier, trial_end


def _lazy_refresh_from_cp(
    tenant_id: str,
) -> tuple[CustomerTier, datetime | None] | None:
    try:
        billing = fetch_billing_information(tenant_id)
    except (requests.RequestException, ValueError) as e:
        logger.warning(
            "Tier lazy-refresh failed for tenant %s; CP unreachable: %s",
            tenant_id,
            e,
        )
        return None

    return _extract_billing_state(billing)


def get_tier(tenant_id: str | None = None) -> Tier:
    if not MULTI_TENANT:
        return _self_hosted_tier()

    tid = tenant_id or get_current_tenant_id()

    try:
        cached = get_cached_tier(tid)
    except RedisError as e:
        # Don't try CP either — likely a wider outage; keep failures cheap.
        logger.warning(
            "Tier Redis read failed for tenant %s; falling back to BUSINESS: %s",
            tid,
            e,
        )
        return Tier.BUSINESS

    if cached is not None:
        return _effective_tier(cached.customer_tier, cached.trial_end)

    fresh = _lazy_refresh_from_cp(tid)
    if fresh is not None:
        fresh_tier, fresh_trial_end = fresh
        try:
            update_tenant_tier(tid, fresh_tier, fresh_trial_end)
        except RedisError as e:
            logger.warning(
                "Tier Redis write failed for tenant %s after CP refresh: %s",
                tid,
                e,
            )
        return _effective_tier(fresh_tier, fresh_trial_end)

    # Don't cache the fallback — next call retries the refresh.
    return Tier.BUSINESS


def require_business_tier_for_sync_access(access_type: AccessType) -> None:
    """Raise FEATURE_NOT_AVAILABLE if SYNC access is requested below BUSINESS.

    Auto-permission-sync requires connector-side permission tracking, which
    is a Business+ feature. Failing at create/edit time means cc-pairs with
    SYNC access only exist on tenants that can actually run the sync —
    instead of letting the row land and silently never sync.

    """
    if access_type != AccessType.SYNC:
        return
    if not tier_at_least(get_tier(), Tier.BUSINESS):
        raise OnyxError(
            OnyxErrorCode.FEATURE_NOT_AVAILABLE,
            "Auto-sync access requires the Business or Enterprise plan.",
        )


def require_business_tier_for_multi_sso() -> None:
    """Gate a second simultaneously enabled SSO provider to Business or
    above. A single enabled provider works at every tier.
    LICENSE_ENFORCEMENT_ENABLED=False passes, matching the sync-access
    guard."""
    if not LICENSE_ENFORCEMENT_ENABLED:
        return
    if not tier_at_least(get_tier(), Tier.BUSINESS):
        raise OnyxError(
            OnyxErrorCode.FEATURE_NOT_AVAILABLE,
            "Multiple enabled SSO providers require the Business or Enterprise plan.",
        )
