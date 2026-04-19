from pathlib import Path

import pytest

from data.plugins.astrbot_plugin_wot.src.application.report.h2i_renderer import (
    H2IRenderer,
)


@pytest.mark.asyncio
async def test_render_report_clears_previous_artifacts_before_fallback_render(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    renderer = H2IRenderer()
    jpg_path = tmp_path / "10001.jpg"
    url_path = tmp_path / "10001.url"
    jpg_path.write_bytes(b"old-jpg")
    url_path.write_text('{"url": "https://old.example/report.jpg"}', encoding="utf-8")

    monkeypatch.setattr(
        "data.plugins.astrbot_plugin_wot.src.application.report.h2i_renderer.is_h2i_enabled",
        lambda: False,
    )

    async def _fake_t2i(html_output: str, report_dir: Path, send_id: str, options):
        assert html_output == "<html></html>"
        assert report_dir == tmp_path
        assert send_id == "10001"
        assert not jpg_path.exists()
        assert not url_path.exists()
        return "https://example.com/report.jpg"

    monkeypatch.setattr(renderer, "_render_with_t2i", _fake_t2i)

    image_url = await renderer.render_report("10001", "<html></html>", tmp_path, {})

    assert image_url == "https://example.com/report.jpg"
