"""Phase 10: storyboard → comic, with a guaranteed SVG fallback."""
from backend.app.providers.base import ImageGenerationProvider, ProviderError
from backend.app.providers.mock import MockImageProvider, MockTextProvider, MockVisionProvider
from backend.app.services.comic import render_comic, svg_panel
from backend.app.schemas.ai import Comic
from palmistry.interpretation import interpret


def _board():
    reading = MockTextProvider().write_reading(interpret(MockVisionProvider().observe(b"x", "right")))
    return MockTextProvider().storyboard(reading)


def test_svg_panel_is_deterministic_data_url():
    b = _board()
    u1 = svg_panel(b.panels[0], b.style)
    u2 = svg_panel(b.panels[0], b.style)
    assert u1 == u2 and u1.startswith("data:image/svg+xml;base64,")


def test_render_comic_with_mock_provider():
    b = _board()
    comic = render_comic(b, MockImageProvider())
    assert isinstance(comic, Comic)
    assert len(comic.panels) == 4
    for p in comic.panels:
        assert p.image_url and p.caption and p.source == "mock"


def test_render_comic_falls_back_when_provider_fails():
    class Broken(ImageGenerationProvider):
        name = "broken"
        def render_panel(self, panel, style):
            raise ProviderError("no image API")
    comic = render_comic(_board(), Broken())
    assert len(comic.panels) == 4
    assert all(p.source == "svg-fallback" for p in comic.panels)
    assert all(p.image_url.startswith("data:image/svg+xml") for p in comic.panels)


def test_render_comic_falls_back_on_empty_url():
    class Empty(ImageGenerationProvider):
        name = "empty"
        def render_panel(self, panel, style):
            return ""
    comic = render_comic(_board(), Empty())
    assert all(p.source == "svg-fallback" for p in comic.panels)


def test_pollinations_builds_url_without_network():
    from backend.app.providers.hf import PollinationsImageProvider
    b = _board()
    url = PollinationsImageProvider().render_panel(b.panels[1], b.style)
    assert url.startswith("https://image.pollinations.ai/prompt/")
    assert "nologo=true" in url


def test_palette_changes_svg():
    b = _board()
    s1 = svg_panel(b.panels[0], b.style)
    # different palette → different bytes
    b.style.palette = "indigo twilight"
    s2 = svg_panel(b.panels[0], b.style)
    assert s1 != s2
