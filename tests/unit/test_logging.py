# tests/unit/test_logging.py
"""Tests for deepresearch.logging module."""

import logging
import sys

from deepresearch.logging import setup_logging, _is_test_env
from deepresearch.config import Settings


class TestIsTestEnv:
    """_is_test_env() 检测 test 环境。"""

    def test_returns_true_when_pytest_in_modules(self):
        """pytest 在 sys.modules 中时应返回 True。"""
        assert "pytest" in sys.modules
        assert _is_test_env() is True

    def test_returns_true_when_env_var_set(self, monkeypatch):
        """PYTEST_CURRENT_TEST 环境变量存在时应返回 True。"""
        with monkeypatch.context() as m:
            m.delitem(sys.modules, "pytest", raising=False)
            m.setenv("PYTEST_CURRENT_TEST", "test_logging.py::test_foo")
            assert _is_test_env() is True


class TestSetupLogging:
    """setup_logging() 行为测试。"""

    def test_sets_root_logger_level(self):
        """应设置 deepresearch root logger 级别。"""
        logger = setup_logging(level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_default_level_is_info(self):
        """默认级别为 INFO。"""
        logger = setup_logging()
        assert logger.level == logging.INFO

    def test_invalid_level_falls_back_to_info(self):
        """无效级别应回退到 INFO。"""
        logger = setup_logging(level="INVALID")
        assert logger.level == logging.INFO

    def test_no_handlers_in_test_env(self):
        """测试环境下不应添加 handler（避免污染 pytest 输出）。"""
        logger = setup_logging(level="DEBUG")
        assert logger.handlers == []
        assert logger.propagate is True

    def test_force_clears_existing_handlers(self):
        """force=True 时应清除已有 handler。"""
        # 先添加一个 fake handler
        root = logging.getLogger("deepresearch")
        root.addHandler(logging.NullHandler())
        assert len(root.handlers) == 1

        # force 重新配置（测试模式下不会添加新的，但会清除旧的）
        setup_logging(force=True)
        assert len(root.handlers) == 0

    def test_file_handler_created_when_log_file_given(self, tmp_path, monkeypatch):
        """提供 log_file 时应创建文件 handler。"""
        # 模拟非测试环境
        monkeypatch.delitem(sys.modules, "pytest", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        log_file = tmp_path / "test.log"
        logger = setup_logging(level="DEBUG", log_file=str(log_file), force=True)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1
        assert logger.propagate is False

        # 写入一条日志验证文件写入
        logger.info("test message")
        # FileHandler 默认有缓冲，关闭后刷新
        file_handlers[0].close()
        content = log_file.read_text(encoding="utf-8")
        assert "test message" in content

    def test_no_file_handler_when_log_file_is_none(self, monkeypatch):
        """不提供 log_file 时不应创建文件 handler。"""
        monkeypatch.delitem(sys.modules, "pytest", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        logger = setup_logging(level="INFO", force=True)
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0

    def test_third_party_loggers_suppressed(self, monkeypatch):
        """应抑制第三方库的日志噪音。"""
        monkeypatch.delitem(sys.modules, "pytest", raising=False)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

        setup_logging(level="DEBUG", force=True)

        noisy_loggers = ["httpx", "urllib3", "trafilatura", "duckduckgo_search", "ddgs"]
        for name in noisy_loggers:
            assert logging.getLogger(name).level == logging.WARNING

    def test_submodule_logger_inherits_level(self):
        """子模块 logger 应继承 deepresearch 根 logger 级别。"""
        setup_logging(level="DEBUG")
        child = logging.getLogger("deepresearch.nodes.research")
        # propagate=True 意味着由根 logger 控制级别
        assert child.level == logging.NOTSET  # NOTSET 表示继承父级
        assert child.getEffectiveLevel() == logging.DEBUG


class TestConfigLoggingSettings:
    """config.py 中的日志相关配置。"""

    def test_log_level_default(self):
        """log_level 默认值为 INFO。"""
        s = Settings()
        assert s.log_level == "INFO"

    def test_log_file_default(self):
        """log_file 默认值为 None。"""
        s = Settings()
        assert s.log_file is None

    def test_log_level_from_env(self, monkeypatch):
        """从环境变量加载 log_level。"""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        s = Settings()
        assert s.log_level == "DEBUG"

    def test_log_file_from_env(self, monkeypatch):
        """从环境变量加载 log_file。"""
        monkeypatch.setenv("LOG_FILE", "logs/deepresearch.log")
        s = Settings()
        assert s.log_file == "logs/deepresearch.log"


class TestIntegration:
    """集成测试：验证日志在各模块中可用。"""

    def test_research_node_logger_exists(self):
        """research node 应定义了 logger。"""
        from deepresearch.nodes.research import logger
        assert logger.name == "deepresearch.nodes.research"

    def test_plan_node_logger_exists(self):
        """plan node 应定义了 logger。"""
        from deepresearch.nodes.plan import logger
        assert logger.name == "deepresearch.nodes.plan"

    def test_tools_logger_exists(self):
        """tools 模块应定义了 logger。"""
        from deepresearch.tools import logger
        assert logger.name == "deepresearch.tools"

    def test_output_logger_exists(self):
        """output 模块应定义了 logger。"""
        from deepresearch.output import logger
        assert logger.name == "deepresearch.output"

    def test_graph_logger_exists(self):
        """graph 模块应定义了 logger。"""
        from deepresearch.graph import logger
        assert logger.name == "deepresearch.graph"
