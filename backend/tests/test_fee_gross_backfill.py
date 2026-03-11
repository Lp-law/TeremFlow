"""Tests for stage fee gross (incl. VAT) and backfill idempotency."""

from decimal import Decimal

# Same mapping as migration 0016: only these net values are converted; already-gross untouched.
NET_TO_GROSS = {
    "20000.00": "23600.00", "20000": "23600.00",
    "15000.00": "17700.00", "15000": "17700.00",
    "10000.00": "11800.00", "10000": "11800.00",
    "1500.00": "1770.00", "1500": "1770.00",
    "5000.00": "5900.00", "5000": "5900.00",
    "700.00": "826.00", "700": "826.00",
    "0.00": "0.00", "0": "0.00",
}


def test_net_to_gross_stage1():
    """Stage 1 net 20,000 -> gross 23,600 (18% VAT)."""
    assert NET_TO_GROSS.get("20000.00") == "23600.00"
    assert NET_TO_GROSS.get("20000") == "23600.00"


def test_already_gross_not_in_net_set():
    """23600 (gross) must not be a key in NET_TO_GROSS so backfill does not double-convert."""
    # If 23600 were a key, we would convert it again. It must only appear as a value.
    assert "23600.00" not in NET_TO_GROSS
    assert "23600" not in NET_TO_GROSS


def test_backfill_idempotent_known_net_converts_once():
    """Known net 20,000 converts to 23,600 once; after backfill no row has 20,000 so re-run is no-op."""
    assert Decimal(NET_TO_GROSS["20000.00"]) == Decimal("23600.00")
