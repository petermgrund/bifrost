"""UI settings kept in the app_settings table.

This is what app_settings is for: values a user changes in the app rather
than in config.yaml, so they follow the tree rather than one browser.
"""

from __future__ import annotations

import re
import sqlite3

THEME_SEED_KEY = "ui.theme_seed"
# the palette bifrost.css paints by default; a seed equal to this is a no-op
DEFAULT_THEME_SEED = "#4a5bae"

_HEX_RE = re.compile(r"\A#?[0-9a-fA-F]{6}\Z")


def normalize_seed(value: str | None) -> str:
    """'4A5BAE' or '#4a5bae' -> '#4a5bae'; anything else is a ValueError"""
    text = (value or "").strip()
    if not _HEX_RE.match(text):
        raise ValueError(f"not a 6 digit hex colour: {value!r}")
    return "#" + text.lstrip("#").lower()


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute(
        "SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value))


def get_theme_seed(conn: sqlite3.Connection) -> str:
    return get_setting(conn, THEME_SEED_KEY, DEFAULT_THEME_SEED)


def set_theme_seed(conn: sqlite3.Connection, seed: str | None) -> str:
    """Validates before writing, so a bad colour never reaches the table"""
    normalized = normalize_seed(seed)
    set_setting(conn, THEME_SEED_KEY, normalized)
    return normalized
