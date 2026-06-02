"""
统一日志配置
================================
提供结构化日志输出，支持文件和控制台双通道。
"""
import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(
    name: str = "travel_assistant",
    log_dir: Path = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    创建日志器，同时输出到控制台和文件。

    Args:
        name: 日志器名称
        log_dir: 日志文件目录 (默认: DATA_DIR/logs)
        level: 日志级别
    Returns:
        配置好的Logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 格式化器
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件handler (可选)
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"travel_assistant_{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


# 默认日志实例
logger = setup_logging()
