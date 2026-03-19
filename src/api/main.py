from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.routers.chat import router as chat_router
from src.api.routers.documents import router as documents_router
from src.api.routers.exports import router as exports_router
from src.api.routers.jobs import router as jobs_router
from src.api.routers.rtm import router as rtm_router
from src.api.routers.tc import router as tc_router
from src.api.routers.validation import router as validation_router
from src.api.routers.web import router as web_router

app = FastAPI(title="QA TC Automation API")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(tc_router)
app.include_router(jobs_router)
app.include_router(validation_router)
app.include_router(rtm_router)
app.include_router(exports_router)
app.include_router(web_router)


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/app/chat", status_code=302)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
