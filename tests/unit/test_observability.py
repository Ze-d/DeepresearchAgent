import pytest
import time
from deepresearch.observability.metrics import NodeMetrics, MetricsCollector


class TestNodeMetrics:
    def test_latency_ms(self):
        t0 = time.perf_counter()
        t1 = t0 + 2.5
        m = NodeMetrics(
            node_name="plan",
            start_time=t0,
            end_time=t1,
            input_tokens=100,
            output_tokens=50,
            llm_calls=1,
        )
        assert m.latency_ms == pytest.approx(2500, rel=0.1)
        assert m.total_tokens == 150

    def test_empty_metrics(self):
        m = NodeMetrics(
            node_name="test",
            start_time=0.0,
            end_time=0.0,
            input_tokens=0,
            output_tokens=0,
            llm_calls=0,
        )
        assert m.latency_ms == 0.0
        assert m.total_tokens == 0


class TestMetricsCollector:
    def test_record_and_summary(self):
        collector = MetricsCollector()

        m1 = NodeMetrics(
            node_name="plan", start_time=0.0, end_time=2.3,
            input_tokens=800, output_tokens=200, llm_calls=1,
        )
        m2 = NodeMetrics(
            node_name="research", start_time=2.3, end_time=7.5,
            input_tokens=15000, output_tokens=3000, llm_calls=5,
        )

        collector.record_node("plan", m1)
        collector.record_node("research", m2)

        summary = collector.summary()
        assert summary["total_tokens"] == 19000
        assert summary["nodes"]["plan"]["tokens"] == 1000
        assert summary["nodes"]["research"]["tokens"] == 18000
        assert summary["nodes"]["plan"]["llm_calls"] == 1
        assert summary["nodes"]["research"]["llm_calls"] == 5

    def test_summary_empty(self):
        collector = MetricsCollector()
        summary = collector.summary()
        assert summary["total_tokens"] == 0
        assert summary["total_latency_ms"] == 0
        assert summary["nodes"] == {}

    def test_errors_tracked(self):
        collector = MetricsCollector()
        m = NodeMetrics(
            node_name="plan", start_time=0.0, end_time=1.0,
            input_tokens=0, output_tokens=0, llm_calls=1,
            errors=["Plan generation failed"],
        )
        collector.record_node("plan", m)
        summary = collector.summary()
        assert summary["nodes"]["plan"]["errors"] == 1
