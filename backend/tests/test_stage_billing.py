"""Tests for fee stage rates and stage-billing (create fee event from performed stages)."""

from decimal import Decimal
from datetime import date

import pytest

from app.models.case import Case
from app.models.enums import CaseStatus, CaseType, FeeEventType
from app.models.fee_stage_rate import FeeStageRate
from app.services.fees import (
    create_stage_billing_event,
    get_billed_codes_for_case,
    get_fee_stage_rates,
)
from app.services.unified import get_unified_summary


def _seed_rates(db):
    # Gross (כולל מע"מ)
    for code, amount in [
        ("COURT_STAGE_1_DEFENSE", Decimal("23600.00")),
        ("COURT_STAGE_2_DAMAGES", Decimal("17700.00")),
        ("APPEAL", Decimal("17700.00")),
    ]:
        db.add(FeeStageRate(code=code, amount_ils=amount, is_active=True))
    db.commit()


@pytest.fixture
def case_with_rates(db):
    c = Case(
        case_reference="T-SB-1",
        case_name="Stage billing test",
        case_type=CaseType.COURT,
        status=CaseStatus.OPEN,
        open_date=date(2024, 1, 1),
        retainer_anchor_date=date(2024, 1, 1),
        deductible_ils_gross=Decimal("5000.00"),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    _seed_rates(db)
    return c


def test_get_fee_stage_rates(db, case_with_rates):
    rates = get_fee_stage_rates(db)
    assert len(rates) >= 3
    codes = [r.code for r in rates]
    assert "COURT_STAGE_1_DEFENSE" in codes
    assert "APPEAL" in codes


def test_fee_stage_rate_stage1_is_gross(db, case_with_rates):
    """Stage 1 must be 23,600 ILS gross (incl. VAT), not 20,000 net."""
    rates = get_fee_stage_rates(db)
    stage1 = next((r for r in rates if r.code == "COURT_STAGE_1_DEFENSE"), None)
    assert stage1 is not None
    assert stage1.amount_ils == Decimal("23600.00")


def test_get_billed_codes_empty(db, case_with_rates):
    codes = get_billed_codes_for_case(db, case_with_rates.id)
    assert codes == []


def test_stage_billing_single_stage1_charges_23600(db, case_with_rates):
    """Creating STAGE_BILLING with only COURT_STAGE_1_DEFENSE must charge 23,600 (gross) everywhere."""
    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE"]
        adjustment = None

    e = create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)
    assert e.computed_amount_ils_gross == Decimal("23600.00")
    assert e.breakdown_json["base_total_selected"] == "23600.00"
    assert e.breakdown_json["delta_total"] == "23600.00"
    assert e.breakdown_json["final_delta_total"] == "23600.00"

    # Unified summary must use gross for fees_by_stages_ils
    summary = get_unified_summary(db, case_with_rates)
    assert summary["fees_by_stages_ils"] == Decimal("23600.00")


def test_create_stage_billing_event_no_adjustment(db, case_with_rates):
    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
        adjustment = None

    e = create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)
    assert e.event_type == FeeEventType.STAGE_BILLING
    assert e.computed_amount_ils_gross == Decimal("41300.00")  # 23600 + 17700 gross
    assert e.breakdown_json is not None
    assert e.breakdown_json["codes_selected"] == ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
    assert e.breakdown_json["codes_already_billed"] == []
    assert e.breakdown_json["new_codes"] == ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
    assert e.breakdown_json["base_total_selected"] == "41300.00"
    assert e.breakdown_json["delta_total"] == "41300.00"
    assert e.breakdown_json["final_delta_total"] == "41300.00"
    db.refresh(case_with_rates)
    assert case_with_rates.performed_fee_stage_codes == ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]


def test_get_billed_codes_after_create(db, case_with_rates):
    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "APPEAL"]
        adjustment = None

    create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)
    codes = get_billed_codes_for_case(db, case_with_rates.id)
    assert set(codes) == {"COURT_STAGE_1_DEFENSE", "APPEAL"}


def test_create_stage_billing_with_discount(db, case_with_rates):
    """Adjustment is amount_ils only (no percent). DISCOUNT: final = delta_total - amount_ils."""
    class Adj:
        kind = "DISCOUNT"
        amount_ils = Decimal("5000.00")
        reason = "הנחה"

    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE"]
        adjustment = Adj()

    e = create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)
    assert e.computed_amount_ils_gross == Decimal("18600.00")  # delta 23600 - 5000
    assert e.breakdown_json["delta_total"] == "23600.00"
    assert e.breakdown_json["adjustment"]["kind"] == "DISCOUNT"
    assert e.breakdown_json["adjustment"].get("percent") is None
    assert e.breakdown_json["final_delta_total"] == "18600.00"


def test_delta_only_then_discount_ils(db, case_with_rates):
    """billed={A,B}, selected={A,B,C}, DISCOUNT amount_ils=10 => event amount = rate(C)-10."""
    class Payload1:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
        adjustment = None

    create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload1(), user_id=1)

    class Adj:
        kind = "DISCOUNT"
        amount_ils = Decimal("10.00")
        reason = ""

    class Payload2:
        event_date = date(2024, 7, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES", "APPEAL"]
        adjustment = Adj()

    e2 = create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload2(), user_id=1)
    # rate(APPEAL) = 17700 gross, minus 10 => 17690
    assert e2.computed_amount_ils_gross == Decimal("17690.00")
    assert e2.breakdown_json["delta_total"] == "17700.00"
    assert e2.breakdown_json["final_delta_total"] == "17690.00"


def test_discount_exceeds_new_charges_returns_400(db, case_with_rates):
    """When discount > delta_total, return 400 'Discount exceeds new charges'."""
    class Adj:
        kind = "DISCOUNT"
        amount_ils = Decimal("25000.00")  # > COURT_STAGE_1_DEFENSE rate 23600
        reason = ""

    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE"]
        adjustment = Adj()

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)
    assert exc_info.value.status_code == 400
    assert "Discount exceeds new charges" in str(exc_info.value.detail)


def test_cumulative_delta_second_call_same_codes_rejects(db, case_with_rates):
    """Submitting same codes again yields no new_codes -> 400 unless confirm_zero."""
    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
        adjustment = None
        confirm_zero_new_codes = False

    create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "No new codes to bill"


def test_cumulative_delta_second_call_confirm_zero_creates_zero_event(db, case_with_rates):
    """With confirm_zero_new_codes=True, same codes creates 0-amount event."""
    class Payload:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
        adjustment = None
        confirm_zero_new_codes = False

    create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload(), user_id=1)

    class PayloadZero:
        event_date = date(2024, 7, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
        adjustment = None
        confirm_zero_new_codes = True

    e2 = create_stage_billing_event(db, case_id=case_with_rates.id, payload=PayloadZero(), user_id=1)
    assert e2.computed_amount_ils_gross == Decimal("0.00")
    assert e2.breakdown_json["new_codes"] == []
    assert e2.breakdown_json["delta_total"] == "0.00"
    assert e2.breakdown_json["final_delta_total"] == "0.00"


def test_cumulative_delta_second_call_add_one_more_code(db, case_with_rates):
    """First bill [A, B]; then [A, B, C] -> second event charges only C."""
    class Payload1:
        event_date = date(2024, 6, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
        adjustment = None

    create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload1(), user_id=1)

    class Payload2:
        event_date = date(2024, 7, 1)
        codes = ["COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES", "APPEAL"]
        adjustment = None

    e2 = create_stage_billing_event(db, case_id=case_with_rates.id, payload=Payload2(), user_id=1)
    assert e2.breakdown_json["codes_selected"] == ["APPEAL", "COURT_STAGE_1_DEFENSE", "COURT_STAGE_2_DAMAGES"]
    assert e2.breakdown_json["new_codes"] == ["APPEAL"]
    assert e2.breakdown_json["delta_total"] == "17700.00"  # APPEAL rate (gross)
    assert e2.computed_amount_ils_gross == Decimal("17700.00")
