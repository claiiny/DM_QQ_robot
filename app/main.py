"""QQ Bot Backend 应用入口模块。

负责创建 FastAPI 应用实例、初始化日志系统，并注册各业务路由。
"""

from fastapi import FastAPI

from app.core.logging import setup_logging
from app.api.qq.router import router as qq_router
from app.api.transfer.router import router as transfer_router

setup_logging()

app = FastAPI(title="QQ Bot Backend", version="0.1.0")

app.include_router(qq_router)
app.include_router(transfer_router)
