from __future__ import annotations

import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
from sqlalchemy.orm import Session
from tenacity import RetryError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.fx_cache import FxRateCache


BOI_SDMX_URL = "https://api.boi.org.il/SDMX/v2/data/EXR/RER_USD_ILS"

# In-memory cache for the current process (Render is stateless, but this still reduces calls).
_mem_cache: dict[dt.date, Decimal] = {}


class FxLookupError(RuntimeError):
    pass


def _q_rate(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
def _fetch_boi_sdmx_json(*, start: dt.date, end: dt.date) -> dict[str, Any]:
    params = {
        "startPeriod": start.isoformat(),
        "endPeriod": end.isoformat(),
        "format": "sdmx-json",
    }
    with httpx.Client(timeout=15) as client:
        r = client.get(BOI_SDMX_URL, params=params, headers={"Accept": "application/json"})
        if r.status_code != 200:
            raise FxLookupError(f"BOI FX request failed: {r.status_code} {r.text[:200]}")
        return r.json()


def _parse_sdmx_json_for_single_rate(data: dict[str, Any]) -> tuple[Decimal, dt.date] | None:
    """
    Tries to parse BOI SDMX JSON and return (rate, rate_date).

    The SDMX-JSON structure has:
    - structure.dimensions.observation[0].values -> dates
    - dataSets[0].series -> series dict (usually single series)
    - observations -> map obsIndex -> [value, ...]
    """
    try:
        datasets = data.get("dataSets") or []
        if not datasets:
            return None
        series_dict = datasets[0].get("series") or {}
        if not series_dict:
            return None
        # pick first series (there should be one)
        first_series = next(iter(series_dict.values()))
        observations = first_series.get("observations") or {}
        if not observations:
            return None

        obs_dim = (
            (data.get("structure") or {})
            .get("dimensions", {})
            .get("observation", [{}])[0]
            .get("values", [])
        )
        if not obs_dim:
            return None

        # We expect a single observation in the requested range; if multiple, take the last.
        last_key = sorted(observations.keys(), key=lambda k: int(k))[-1]
        rate_val = observations[last_key][0]
        date_id = obs_dim[int(last_key)].get("id") or obs_dim[int(last_key)].get("name")
        if not date_id:
            return None
        rate_date = dt.date.fromisoformat(str(date_id))
        rate = _q_rate(Decimal(str(rate_val)))
        return rate, rate_date
    except Exception:
        return None


def get_usd_ils_rate(target_date: dt.date, db: Session | None = None) -> tuple[Decimal, dt.date]:
    """
    Fetch USD/ILS rate for target_date.

    If target_date is a non-business day / missing data, search backwards up to 10 days.
    Caches in-memory and optionally in DB (FxRateCache).
    """
    # In-memory cache is keyed by the actual rate date.
    if target_date in _mem_cache:
        return _mem_cache[target_date], target_date

    if db is not None:
        cached = db.query(FxRateCache).filter(FxRateCache.rate_date == target_date).first()
        if cached:
            rate = _q_rate(Decimal(str(cached.rate_usd_ils)))
            _mem_cache[target_date] = rate
            return rate, target_date

    for i in range(0, 11):
        d = target_date - dt.timedelta(days=i)

        if d in _mem_cache:
            return _mem_cache[d], d

        if db is not None:
            cached = db.query(FxRateCache).filter(FxRateCache.rate_date == d).first()
            if cached:
                rate = _q_rate(Decimal(str(cached.rate_usd_ils)))
                _mem_cache[d] = rate
                return rate, d

        try:
            data = _fetch_boi_sdmx_json(start=d, end=d)
        except RetryError as e:
            # Common local-dev failure: no outbound DNS/network. Suggest import-style path without changing logic.
            hint = " (Tip: if you are offline, create the case using deductible_ils_gross instead of deductible_usd.)"
            raise FxLookupError(f"BOI FX request failed (network/timeout): {e.last_attempt.exception()}{hint}") from e
        parsed = _parse_sdmx_json_for_single_rate(data)
        if parsed is None:
            continue
        rate, rate_date = parsed
        _mem_cache[rate_date] = rate
        if db is not None:
            existing = db.query(FxRateCache).filter(FxRateCache.rate_date == rate_date).first()
            if not existing:
                db.add(FxRateCache(rate_date=rate_date, rate_usd_ils=rate, source="BOI"))
                db.commit()
        return rate, rate_date

    raise FxLookupError(f"No BOI USD/ILS rate found for {target_date.isoformat()} (searched back 10 days)")


