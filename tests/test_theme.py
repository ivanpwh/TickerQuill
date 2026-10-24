import pytest

pytest.importorskip("tkinter")
from tickerquill import theme  # noqa: E402


@pytest.fixture(autouse=True)
def restore_theme():
    before = theme.current
    yield
    theme.apply(before)


def test_every_theme_defines_all_roles_with_distinct_main_colours():
    for name, colours in theme.THEMES.items():
        assert set(colours) == set(theme.ROLES), name
        main = [colours[r] for r in ("BG", "FG", "DIM", "AMBER", "RED", "CYAN")]
        assert len(set(main)) == len(main), f"{name} reuses a colour; live re-colouring would be ambiguous"


def test_mix_endpoints_and_midpoint():
    assert theme.mix("#000000", "#ffffff", 0) == "#000000"
    assert theme.mix("#000000", "#ffffff", 1) == "#ffffff"
    assert theme.mix("#000000", "#ffffff", 0.5) == "#808080"


def test_apply_returns_previous_palette_and_unknown_falls_back():
    theme.apply("dark")
    old = theme.apply("light")
    assert old["BG"] == theme.THEMES["dark"]["BG"] and theme.T.BG == theme.THEMES["light"]["BG"]
    theme.apply("no-such-theme")
    assert theme.current == theme.DEFAULT


def test_system_theme_resolves_to_dark_or_light():
    assert theme.resolve("system") in ("dark", "light")
