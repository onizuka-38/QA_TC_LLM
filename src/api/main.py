from fastapi import FastAPI

from src.api.routers.documents import router as documents_router
from src.api.routers.exports import router as exports_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.rtm import router as rtm_router
from src.api.routers.tc import router as tc_router
from src.api.routers.validation import router as validation_router

app = FastAPI(title="QA TC Automation API")

app.include_router(documents_router)
app.include_router(tc_router)
app.include_router(jobs_router)
app.include_router(validation_router)
app.include_router(rtm_router)
app.include_router(exports_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
