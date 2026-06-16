from deepresearch.observability.metrics import NodeMetrics, MetricsCollector
from deepresearch.observability.callbacks import ObservabilityCallback

__all__ = ["NodeMetrics", "MetricsCollector", "ObservabilityCallback"]

# OTel 组件：如果 opentelemetry 未安装则不可用
try:
    from deepresearch.observability.otel import setup_otel, workflow_span
    from deepresearch.observability.otel_callback import OTelCallbackHandler, _trace_node

    __all__.extend(["setup_otel", "workflow_span", "OTelCallbackHandler", "_trace_node"])
except ImportError:
    pass
