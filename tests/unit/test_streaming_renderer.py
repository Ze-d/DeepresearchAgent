from rich.console import Console
from deepresearch.streaming.renderer import StreamRenderer


class TestStreamRenderer:
    def test_create(self):
        console = Console(force_terminal=True, color_system=None)
        renderer = StreamRenderer(console)
        assert renderer is not None

    def test_render_node_start(self):
        console = Console(force_terminal=True, color_system=None)
        renderer = StreamRenderer(console)
        renderer.render_node_start("plan")
        renderer.render_node_start("research")

    def test_render_node_done(self):
        console = Console(force_terminal=True, color_system=None)
        renderer = StreamRenderer(console)
        renderer.render_node_done("plan", {"status": "planned"})
        renderer.render_node_done("research", {"sources": [{"title": "test"}]})

    def test_render_done_marks_completed(self):
        console = Console(force_terminal=True, color_system=None)
        renderer = StreamRenderer(console)
        renderer.render_node_done("final", {"status": "completed"})
        assert "final" in renderer._completed

    def test_disabled_mode(self):
        """disabled=True 时所有 render 方法不抛异常也不追踪"""
        console = Console(force_terminal=True, color_system=None)
        renderer = StreamRenderer(console, enabled=False)
        renderer.render_node_start("plan")
        renderer.render_node_done("plan", {})
        assert "plan" not in renderer._completed
