import datetime as dt

from app.services.retainer import get_retainer_start_month


def test_retainer_start_month_jan_to_jun_starts_next_month():
    assert get_retainer_start_month(dt.date(2026, 1, 10)) == dt.date(2026, 2, 1)
    assert get_retainer_start_month(dt.date(2026, 6, 30)) == dt.date(2026, 7, 1)


def test_retainer_start_month_jul_to_dec_starts_next_january():
    assert get_retainer_start_month(dt.date(2026, 7, 1)) == dt.date(2027, 1, 1)
    assert get_retainer_start_month(dt.date(2026, 12, 31)) == dt.date(2027, 1, 1)


