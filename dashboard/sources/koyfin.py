from ..config import CFG


class NotConfigured(RuntimeError):
    pass


def fetch(*args, **kwargs):
    if not CFG.koyfin_api_key:
        raise NotConfigured("KOYFIN_API_KEY not set")
    raise NotConfigured(
        "Koyfin does not currently expose a public API; configure CSV exports under "
        "data/manual/ and use csv_drop instead."
    )
