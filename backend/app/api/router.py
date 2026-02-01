from fastapi import APIRouter

from app.api.routes import analytics, auth, backups, cases, expenses, fee_events, import_excel, notifications, retainers, tasks

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(expenses.router, prefix="/cases/{case_id}/expenses", tags=["expenses"])
api_router.include_router(retainers.router, prefix="/cases/{case_id}/retainer", tags=["retainer"])
api_router.include_router(fee_events.router, prefix="/cases/{case_id}/fees", tags=["fees"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(import_excel.router, prefix="/import", tags=["import"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(backups.router, prefix="/backups", tags=["backups"])


