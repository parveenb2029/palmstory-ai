"""Phase 5 provider tests — mocks are deterministic; registry respects config."""
import importlib
import os

from backend.app.providers.mock import MockImageProvider, MockTextProvider, MockVisionProvider
from backend.app.providers.base import VisionProvider, with_fallback, ProviderError
from backend.app.schemas.ai import PalmObservation, Reading, Storyboard


def test_mock_vision_is_valid_and_deterministic():
    v = MockVisionProvider()
    a = v.observe(b"same-bytes", "right")
    b = v.observe(b"same-bytes", "right")
    assert isinstance(a, PalmObservation) and a.hand == "right"
    assert len(a.observations) == 4
    assert a == b  # deterministic
    for o in a.observations:
        assert 0.0 <= o.confidence <= 1.0


def test_mock_text_and_storyboard_schema():
    t = MockTextProvider()
    obs = MockVisionProvider().observe(b"x", "left")
    from palmistry.interpretation import interpret
    reading = t.write_reading(interpret(obs))
    assert isinstance(reading, Reading) and reading.title
    board = t.storyboard(reading)
    assert isinstance(board, Storyboard) and len(board.panels) == 4
    assert board.style.character and board.logline
    assert [p.beat for p in board.panels] == ["setup", "rising", "turn", "resolution"]


def test_mock_image_renders_panel_data_url():
    from palmistry.interpretation import interpret
    reading = MockTextProvider().write_reading(interpret(MockVisionProvider().observe(b"x", "right")))
    board = MockTextProvider().storyboard(reading)
    url = MockImageProvider().render_panel(board.panels[0], board.style)
    assert isinstance(url, str) and url.startswith("data:image/svg+xml")


def test_fallback_wrapper_uses_fallback_on_error():
    class Broken(VisionProvider):
        name = "broken"
        def observe(self, image, hand):
            raise ProviderError("boom")
    proxy = with_fallback(Broken(), MockVisionProvider())
    out = proxy.observe(b"x", "right")
    assert isinstance(out, PalmObservation)  # fell back to mock
    assert proxy.name == "broken->mock"


def _reload_registry(**env):
    for k, v in env.items():
        os.environ[k] = v
    import backend.app.providers.registry as reg
    return importlib.reload(reg)


def test_registry_defaults_to_mock():
    reg = _reload_registry(DEV_MOCK_AI="true")
    assert reg.get_vision_provider().name == "mock"
    assert reg.active_providers()["mocks_forced"] is True


def test_registry_selects_real_when_mocks_off():
    reg = _reload_registry(DEV_MOCK_AI="false", VISION_PROVIDER="huggingface",
                           TEXT_PROVIDER="huggingface", IMAGE_PROVIDER="pollinations",
                           PROVIDER_FALLBACK_MOCK="true")
    # with fallback on, the name is the proxy "real->mock"
    assert reg.get_vision_provider().name.startswith("huggingface")
    assert reg.get_image_provider().name.startswith("pollinations")
    # reset for other tests
    _reload_registry(DEV_MOCK_AI="true")


def test_gemini_selectable_and_falls_back_without_key(monkeypatch):
    """Gemini can be selected; with no API key it degrades to mock (never crashes)."""
    import importlib
    monkeypatch.setenv("DEV_MOCK_AI", "false")
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("TEXT_PROVIDER", "gemini")
    monkeypatch.setenv("PROVIDER_FALLBACK_MOCK", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from backend.app.providers import registry
    importlib.reload(registry)
    # observe with no key → ProviderError inside → fallback returns a mock observation
    obs = registry.get_vision_provider().observe(b"not-a-real-image", "right")
    assert obs.hand == "right" and len(obs.observations) >= 1
    importlib.reload(registry)  # restore default for other tests
