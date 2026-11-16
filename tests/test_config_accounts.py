import pytest

from bifrost.core.config import ConfigError, load_config

GRAMPS = 'gramps: {base_url: "http://g/api", username: u, password: p, public_url: "https://g.example/"}\n'
BASE = GRAMPS + 'paperless: {base_url: "http://p", api_token: t}\n'


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


def test_paperless_is_optional(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(GRAMPS)
    assert load_config(path).paperless.base_url == ""
    path.write_text(GRAMPS + 'paperless: {base_url: "http://p"}\n')
    with pytest.raises(ConfigError):
        load_config(path)


def test_previews_prefix_gets_a_trailing_slash(tmp_path):
    cfg = _load(tmp_path, """\
immich: {base_url: "http://i", previews_prefix: immich-previews}
""")
    assert cfg.sync_immich.previews_prefix == "immich-previews/"


def test_previews_prefix_defaults_empty(tmp_path):
    cfg = _load(tmp_path, 'immich: {base_url: "http://i"}\n')
    assert cfg.sync_immich.previews_prefix == ""


def test_paperless_webhook_token(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(GRAMPS + 'paperless: {base_url: "http://p", api_token: t, webhook_token: " s3cret "}\n')
    assert load_config(path).sync_paperless.webhook_token == "s3cret"


def test_paperless_webhook_token_defaults_off(tmp_path):
    assert _load(tmp_path, "").sync_paperless.webhook_token == ""


def test_gramps_public_url_reaches_both_syncs(tmp_path):
    cfg = _load(tmp_path, "")
    assert cfg.sync_paperless.gramps_public_url == cfg.sync_immich.gramps_public_url == "https://g.example"


def test_fields_and_tags_by_name_or_id(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(GRAMPS + """\
paperless:
  base_url: "http://p"
  api_token: t
  gramps_id_field: Gramps ID
  gramps_url_field: "14"
  date_qualifier_field: 20
  transcribed_tag: transcribed
""")
    sp = load_config(path).sync_paperless
    assert (sp.gramps_id_field_id, sp.gramps_url_field_id) == ("Gramps ID", 14)
    assert (sp.date_qualifier_field_id, sp.transcription_tag_id) == (20, "transcribed")


def test_the_old_layout_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="old config layout"):
        _load(tmp_path, "sync: {paperless: {webhook_token: x}}\n")


def test_codes_can_be_turned_off(tmp_path):
    on = _load(tmp_path, 'immich: {base_url: "http://i"}\n')
    assert on.codes and on.sync_paperless.codes and on.sync_immich.id_tag_prefix == "ID"
    off = _load(tmp_path, 'codes: false\nimmich: {base_url: "http://i"}\n')
    assert not (off.codes or off.sync_paperless.codes or off.sync_immich.codes)
    assert off.sync_immich.id_tag_prefix == ""


def test_the_translation_marker_can_be_set(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(GRAMPS + 'paperless: {base_url: "http://p", api_token: t, translation_marker: " --- Deutsch --- "}\n')
    assert load_config(path).sync_paperless.translation_marker == "--- Deutsch ---"
    assert _load(tmp_path, "").sync_paperless.translation_marker == "======== ENGLISH TRANSLATION ========"
