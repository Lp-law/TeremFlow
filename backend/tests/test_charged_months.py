"""
Unit tests for count_charged_months (retainer charged-months counting).

Rule (see retainer.count_charged_months docstring):
- anchor_date is treated as first-of-month (start of that month).
- effective_end_date can be any day; we use the month containing that day as the last charged month.
- If snapshot_through_month is set, start = first day of the month *after* snapshot_through_month.
- Count = number of calendar months from start to end inclusive.
"""
import datetime as dt

import pytest

from app.services.retainer import count_charged_months


def test_same_month():
    """Same month: anchor July 1, end July 15 -> 1 month (July only)."""
    anchor = dt.date(2024, 7, 1)
    effective_end = dt.date(2024, 7, 15)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 1


def test_same_month_first_day():
    """Anchor and end on same first-of-month -> 1."""
    anchor = dt.date(2024, 7, 1)
    effective_end = dt.date(2024, 7, 1)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 1


def test_across_year_boundary():
    """July 2024 to June 2025 -> 12 months."""
    anchor = dt.date(2024, 7, 1)
    effective_end = dt.date(2025, 6, 1)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 12


def test_frozen_date_mid_month():
    """Anchor July 1 2024, effective end Feb 15 2025 -> 8 months (Jul through Feb)."""
    anchor = dt.date(2024, 7, 1)
    effective_end = dt.date(2025, 2, 15)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 8


def test_anchor_normalized_to_first_of_month():
    """Anchor passed as mid-month is normalized to first of that month."""
    anchor = dt.date(2024, 7, 15)
    effective_end = dt.date(2024, 7, 31)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 1


def test_end_before_start_zero():
    """Effective end before start -> 0."""
    anchor = dt.date(2024, 7, 1)
    effective_end = dt.date(2024, 6, 30)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 0


def test_two_months():
    """July to August -> 2."""
    anchor = dt.date(2024, 7, 1)
    effective_end = dt.date(2024, 8, 20)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=None) == 2


def test_with_snapshot_through_start_after_snapshot():
    """Snapshot through June 2024 -> first accrual month is July 2024; end July 15 -> 1."""
    anchor = dt.date(2024, 1, 1)
    snapshot_through = dt.date(2024, 6, 1)
    effective_end = dt.date(2024, 7, 15)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=snapshot_through) == 1


def test_with_snapshot_through_multiple_months():
    """Snapshot through June 2024 -> start July 2024; end Feb 2025 -> 8."""
    anchor = dt.date(2024, 1, 1)
    snapshot_through = dt.date(2024, 6, 30)
    effective_end = dt.date(2025, 2, 15)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=snapshot_through) == 8


def test_with_snapshot_end_before_start_zero():
    """Snapshot through Dec 2024 -> start Jan 2025; end Dec 2024 -> 0."""
    anchor = dt.date(2024, 7, 1)
    snapshot_through = dt.date(2024, 12, 1)
    effective_end = dt.date(2024, 12, 31)
    assert count_charged_months(anchor, effective_end, snapshot_through_month=snapshot_through) == 0
