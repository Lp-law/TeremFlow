import datetime as dt
from decimal import Decimal

import pytest

import app.services.boi_fx as boi_fx


def _sdmx_single(rate_date: dt.date, rate: Decimal) -> dict:
    # Minimal SDMX-JSON shape expected by our parser.
    return {
        "structure": {
            "dimensions": {
                "observation": [
                    {"values": [{"id": rate_date.isoformat(), "name": rate_date.isoformat()}]},
                ]
            }
        },
        "dataSets": [
            {
                "series": {
                    "0:0:0:0": {
                        "observations": {"0": [float(rate)]},
                    }
                }
            }
        ],
    }


def test_fx_lookup_falls_back_to_previous_day(monkeypatch):
    boi_fx._mem_cache.clear()
    target = dt.date(2026, 1, 11)
    prev = dt.date(2026, 1, 10)

    def fake_fetch(*, start: dt.date, end: dt.date):
        if start == target:
            return {}  # no data, forces fallback
        if start == prev:
            return _sdmx_single(prev, Decimal("3.700000"))
        return {}

    monkeypatch.setattr(boi_fx, "_fetch_boi_sdmx_json", fake_fetch)
    rate, used = boi_fx.get_usd_ils_rate(target, db=None)
    assert rate == Decimal("3.700000")
    assert used == prev


def test_fx_lookup_errors_after_10_days(monkeypatch):
    boi_fx._mem_cache.clear()
    def fake_fetch(*, start: dt.date, end: dt.date):
        return {}

    monkeypatch.setattr(boi_fx, "_fetch_boi_sdmx_json", fake_fetch)
    with pytest.raises(boi_fx.FxLookupError):
        boi_fx.get_usd_ils_rate(dt.date(2026, 1, 11), db=None)


