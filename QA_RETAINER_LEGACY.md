# Manual QA: Retainer LEGACY + End Date (Goals A/B/C)

## Goal A — LEGACY in "שכ״ט ששולם עד כה (תיאורטי)"

1. **Case with LEGACY payments:** Pick (or create) a case that has retainer payments with note starting with `LEGACY` (e.g. from "הוסף ריטיינר עבר (LEGACY) בטווח").
2. **Overview tab (סקירה):** Open case → סקירה. Confirm "שכ״ט ששולם עד כה (תיאורטי)" includes the legacy amount (value = regular theoretical + legacy theoretical).
3. **Retainer tab:** Confirm "כולל LEGACY: X" shows when legacy > 0 and total theoretical matches overview.
4. **Debug (admin):** `GET /cases/{id}/retainer/debug-theoretical` — check `legacy_months_count`, `legacy_theoretical_ils`, `regular_theoretical_ils`, `retainer_charged_to_date_ils` = regular + legacy.

## Goal B — LEGACY range feature

5. **Button:** In Retainer tab (as admin), confirm button "הוסף ריטיינר עבר (LEGACY) בטווח" is visible.
6. **Range:** Open modal, set e.g. Jan 2024–Jun 2024, submit. Confirm 6 new payments appear in ledger; notes start with `LEGACY`.
7. **Refresh:** Reload case; overview "שכ״ט ששולם עד כה (תיאורטי)" should still include those 6 months (by formula: 6 × monthly gross).

## Goal C — Retainer end date

8. **Set end date:** In Retainer tab set "תאריך סיום" to e.g. 2024-06-30, save. Refresh page — field should show 2024-06-30.
9. **Month count:** With anchor 2024-01-01 and end 2024-06-30, charged months = 6; with end 2024-02-01 = 2.
10. **Clear end date:** Set "תאריך סיום" to empty and save; refresh — field should be empty and effective end = today (or frozen date).
