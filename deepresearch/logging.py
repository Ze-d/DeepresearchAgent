"""DeepResearch Agent 日志配置模块。

提供统一的日志初始化函数 `setup_logging()`，支持：
- 控制台输出（rich 格式化）
- 文件持久化
- 第三方库日志级别控制
- 测试环境检测（避免污染 pytest 输出）
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


def _is_test_env() -> bool:
    """检测是否在 pytest 环境中运行。"""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str | Path] = None,
    *,
    force: bool = False,
) -> logging.Logger:
    """初始化 DeepResearch Agent 全局日志配置。

    约定：
    - 测试环境下只配置级别，不添加 handler（避免污染 pytest 输出）。
    - 生产 / 开发环境下配置：
      - 控制台 handler（RichHandler，彩色结构化输出）
      - 可选的文件 handler（纯文本，适合持久化和事后排查）

    Args:
        level: 日志级别，支持 "DEBUG", "INFO", "WARNING", "ERROR"。
        log_file: 日志文件路径。为 None 时不输出文件日志。
        force: 强制重新配置（即使已经有 handler）。

    Returns:
        deepresearch 根 logger 实例。
    """
    root_logger = logging.getLogger("deepresearch")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # force 模式或测试环境中需要先清理已有 handler
    if force:
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)

    if _is_test_env():
        # 测试模式：不添加 handler，依赖 pytest 的 caplog fixture
        root_logger.propagate = True
        return root_logger

    if root_logger.handlers and not force:
        return root_logger

    # 清除已有 handlers（首次配置）
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # ——— 控制台 handler（Rich） ———
    try:
        from rich.logging import RichHandler

        console_handler = RichHandler(
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            show_level=True,
            show_path=False,
        )
    except ImportError:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)-8s %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)

    # ——— 文件 handler（纯文本，完整格式化） ———
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # 文件始终记录 DEBUG 级别
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)

    # 抑制第三方库的 DEBUG/INFO 噪音
    for noisy in ("httpx", "urllib3", "trafilatura", "duckduckgo_search", "ddgs"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root_logger.propagate = False

    return root_logger
