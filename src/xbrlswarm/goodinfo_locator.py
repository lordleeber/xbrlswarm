"""Stable Goodinfo announcement locator from its verified URL identity."""

from __future__ import annotations

from urllib.parse import urlencode

from .goodinfo_detail import _locator, _normalized_subject

_PREFIX = "goodinfo:announcement:"


def goodinfo_announcement_locator(detail_url: str) -> str:
    """Encode STOCK_ID, CLAIM_TIME and normalized SUBJECT in a fixed order.

    The URL itself remains available separately as source_url. This locator
    does not depend on Goodinfo's accepted /tw/ versus /tw2/ page paths,
    query-parameter order, percent-encoding choices or extra query fields.
    """

    stock_id, claim_time, subject = _locator(detail_url)
    identity = urlencode((
        ("STOCK_ID", stock_id),
        ("CLAIM_TIME", claim_time.strftime("%Y/%m/%d %H:%M:%S")),
        ("SUBJECT", _normalized_subject(subject)),
    ))
    return _PREFIX + identity


def _same_stored_locator(stored: str, expected: str) -> bool:
    """Recognize a Step-38 URL locator without rewriting immutable evidence."""

    if stored == expected:
        return True
    if stored.startswith(_PREFIX):
        return False
    try:
        return goodinfo_announcement_locator(stored) == expected
    except ValueError:
        return False
