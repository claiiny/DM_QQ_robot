"""日志配置模块。

集中管理日志初始化，使用 RotatingFileHandler 实现日志轮转，
避免单文件过大。所有模块通过 logging.getLogger(__name__) 获取各自的 logger。
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent.parent / "app.log"


def setup_logging() -> None:
    """初始化全局日志配置：输出到文件，单文件 10MB，保留 5 个备份。"""
    handler = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(handler)
