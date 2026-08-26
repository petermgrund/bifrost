import pytest

from bifrost.core.config import ConfigError, load_config

BASE = """\
gramps: {base_url: "http://g/api", username: u, password: p}
paperless: {base_url: "http://p", api_token: t}
"""


def _load(tmp_path, immich_block):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(BASE + immich_block)
    return load_config(cfg)


def test_accounts_list(tmp_path):
    cfg = _load(tmp_path, """\
immich:
  base_url: "http://i"
  accounts:
    - {api_key: k1, label: fh}
    - {api_key: k2, label: peter}
""")
    assert [a.api_key for a in cfg.immich.accounts] == ["k1", "k2"]
    assert [a.label for a in cfg.immich.accounts] == ["fh", "peter"]


def test_account_label_defaults(tmp_path):
    cfg = _load(tmp_path, """\
immich:
  base_url: "http://i"
  accounts:
    - {api_key: k1}
""")
    assert cfg.immich.accounts[0].label == "account 1"


def test_legacy_keys_map_to_accounts(tmp_path):
    cfg = _load(tmp_path, """\
immich: {base_url: "http://i", api_key: k1, partner_api_key: k2}
""")
    assert [a.api_key for a in cfg.immich.accounts] == ["k1", "k2"]
    assert [a.label for a in cfg.immich.accounts] == ["primary", "partner"]


def test_legacy_primary_only(tmp_path):
    cfg = _load(tmp_path, 'immich: {base_url: "http://i", api_key: k1}\n')
    assert [a.label for a in cfg.immich.accounts] == ["primary"]


def test_mixing_shapes_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, """\
immich:
  base_url: "http://i"
  api_key: k1
  accounts: [{api_key: k2}]
""")


def test_three_accounts_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, """\
immich:
  base_url: "http://i"
  accounts: [{api_key: a}, {api_key: b}, {api_key: c}]
""")


def test_account_without_api_key_is_an_error(tmp_path):
    with pytest.raises(ConfigError):
        _load(tmp_path, """\
immich:
  base_url: "http://i"
  accounts: [{label: nope}]
""")


def test_no_immich_section_means_no_accounts(tmp_path):
    cfg = _load(tmp_path, "")
    assert cfg.immich.accounts == ()


def test_legacy_partner_key_alone_stays_disabled(tmp_path):
    cfg = _load(tmp_path, 'immich: {base_url: "http://i", partner_api_key: k2}\n')
    assert cfg.immich.accounts == ()
