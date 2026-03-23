from fastapi import APIRouter

from app.api.routes import activity, admin, analytics, auth, backups, cases, claims_reports, deductible, expenses, fee_events, fee_stage_rates, import_excel, notifications, reports, retainers, tasks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(expenses.router, prefix="/cases/{case_id}/expenses", tags=["expenses"])
api_router.include_router(deductible.router, prefix="/cases/{case_id}/deductible", tags=["deductible"])
api_router.include_router(retainers.router, prefix="/cases/{case_id}/retainer", tags=["retainer"])
api_router.include_router(fee_events.router, prefix="/cases/{case_id}/fees", tags=["fees"])
api_router.include_router(fee_stage_rates.router, prefix="/fee-stage-rates", tags=["fee-stage-rates"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(import_excel.router, prefix="/import", tags=["import"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(backups.router, prefix="/backups", tags=["backups"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(activity.router, prefix="/activity", tags=["activity"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(claims_reports.router, prefix="/claims-reports", tags=["claims-reports"])


