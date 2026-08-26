import pytest

from bifrost.core import db, settings


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "s.db")
    yield c
    c.close()


def test_unset_seed_falls_back_to_the_default(conn):
    assert settings.get_theme_seed(conn) == settings.DEFAULT_THEME_SEED


def test_seed_round_trips(conn):
    settings.set_theme_seed(conn, "#2E7D32")
    assert settings.get_theme_seed(conn) == "#2e7d32"


def test_seed_is_replaced_not_duplicated(conn):
    settings.set_theme_seed(conn, "#111111")
    settings.set_theme_seed(conn, "#222222")
    assert settings.get_theme_seed(conn) == "#222222"
    rows = conn.execute("SELECT COUNT(*) FROM app_settings WHERE key=?",
                        (settings.THEME_SEED_KEY,)).fetchone()[0]
    assert rows == 1


def test_a_bare_hex_is_accepted_and_normalized():
    assert settings.normalize_seed("4A5BAE") == "#4a5bae"
    assert settings.normalize_seed("  #ABCDEF  ") == "#abcdef"


@pytest.mark.parametrize("bad", ["", "#12345", "#1234567", "red", "#ggghhh", None, "#12g456"])
def test_garbage_seeds_are_refused(bad):
    with pytest.raises(ValueError):
        settings.normalize_seed(bad)


def test_setting_a_garbage_seed_writes_nothing(conn):
    with pytest.raises(ValueError):
        settings.set_theme_seed(conn, "nope")
    assert conn.execute("SELECT COUNT(*) FROM app_settings").fetchone()[0] == 0


def test_generic_settings_helpers(conn):
    assert settings.get_setting(conn, "missing.key", "fallback") == "fallback"
    settings.set_setting(conn, "some.key", "value")
    assert settings.get_setting(conn, "some.key") == "value"
