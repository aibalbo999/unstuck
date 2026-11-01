"""Engineering-only release policy. No environment, API or ledger switch enables canary."""


def require_canary_enabled():
    """Fail before source/credential reads, reservations, output or child work.

    Future activation requires a reviewed code change and the separate source,
    billing, budget and campaign acceptance evidence. This is not a controller.
    """
    raise RuntimeError('canary is disabled in this engineering release')


def status():
    return {'canary_enabled':False,'release_scope':'engineering_only',
            'live_qualification_verified':False,'activation_requires_reviewed_release':True}
