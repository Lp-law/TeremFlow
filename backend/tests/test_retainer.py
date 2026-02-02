import datetime as dt
from decimal import Decimal

from app.services.retainer import (
    get_retainer_anchor_date,
    get_retainer_start_month,
    retainer_gross_for_month,
    vat_rate_for_month,
)


def test_retainer_anchor_date_jan_to_jun_july_same_year():
    """Case opened Jan-Jun -> anchor is July of same year."""
    assert get_retainer_anchor_date(dt.date(2026, 2, 15)) == dt.date(2026, 7, 1)
    assert get_retainer_anchor_date(dt.date(2026, 1, 1)) == dt.date(2026, 7, 1)
    assert get_retainer_anchor_date(dt.date(2026, 6, 30)) == dt.date(2026, 7, 1)


def test_retainer_anchor_date_jul_to_dec_january_next_year():
    """Case opened Jul-Dec -> anchor is January of next year."""
    assert get_retainer_anchor_date(dt.date(2026, 10, 1)) == dt.date(2027, 1, 1)
    assert get_retainer_anchor_date(dt.date(2026, 7, 1)) == dt.date(2027, 1, 1)
    assert get_retainer_anchor_date(dt.date(2026, 12, 31)) == dt.date(2027, 1, 1)


def test_retainer_start_month_from_anchor():
    """First accrual month = anchor date (first of month)."""
    assert get_retainer_start_month(dt.date(2026, 7, 1)) == dt.date(2026, 7, 1)
    assert get_retainer_start_month(dt.date(2027, 1, 1)) == dt.date(2027, 1, 1)


def test_vat_rate_dec_2024():
    assert vat_rate_for_month(dt.date(2024, 12, 1)) == Decimal("0.17")


def test_vat_rate_jan_2025():
    assert vat_rate_for_month(dt.date(2025, 1, 1)) == Decimal("0.18")


def test_retainer_gross_dec_2024():
    """945 + 17% VAT = 1105.65"""
    assert retainer_gross_for_month(dt.date(2024, 12, 1)) == Decimal("1105.65")


def test_retainer_gross_jan_2025():
    """945 + 18% VAT = 1115.10"""
    assert retainer_gross_for_month(dt.date(2025, 1, 1)) == Decimal("1115.10")


