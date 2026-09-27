from fastapi import FastAPI

from app.api.api_qq import router as qq_router
from app.api.api_transfer import router as transfer_router

app = FastAPI(title="QQ Bot Backend", version="0.1.0")

app.include_router(qq_router)
app.include_router(transfer_router)
