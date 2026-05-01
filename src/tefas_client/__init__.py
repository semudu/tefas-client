"""tefas_client – TEFAS fund data client.

Public API::

    from tefas_client import Tefas, Fund, History, Allocation
    from tefas_client import FundOverview, UmbrellaFundType, Founder
"""

from __future__ import annotations

from ._models import Allocation, Fund, FundOverview, Founder, History, UmbrellaFundType
from .exceptions import EmptyResponseError, RateLimitError, TefasError
from ._tefas import FundType, Tefas

__all__ = [
    "Tefas",
    "FundType",
    "Fund",
    "History",
    "Allocation",
    "FundOverview",
    "UmbrellaFundType",
    "Founder",
    "TefasError",
    "RateLimitError",
    "EmptyResponseError",
]

__version__ = "1.0.0"
try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("tefas-client")
except PackageNotFoundError:  # pragma: no cover
    pass
