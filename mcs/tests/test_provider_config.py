"""Unit tests for mcs.config.load_providers (SPEC.md §13). Offline, no API key
needed -- separate from the live capability suites in mcs/suites."""

import textwrap

import pytest

from mcs.config import load_providers


def _write(tmp_path, content):
    path = tmp_path / "providers.yaml"
    path.write_text(textwrap.dedent(content).strip() + "\n")
    return str(path)


def test_happy_path_two_providers(tmp_path, monkeypatch):
    monkeypatch.setenv("CSCS_KEY", "secret-1")
    monkeypatch.setenv("RCP_KEY", "secret-2")
    path = _write(
        tmp_path,
        """
        providers:
          cscs:
            base_url: https://cscs.example/v1/
            api_key_env: CSCS_KEY
            model: swiss-ai/Apertus-8B
          rcp:
            base_url: https://rcp.example/v1
            api_key_env: RCP_KEY
            model: other-org/other-model
            timeout: 30
            rate_limit: 5
        """,
    )
    cfgs = load_providers(path)

    assert [c.label for c in cfgs] == ["cscs", "rcp"]
    assert cfgs[0].api_base == "https://cscs.example/v1"  # trailing slash stripped
    assert cfgs[0].api_key == "secret-1"
    assert cfgs[0].model == "swiss-ai/Apertus-8B"
    assert cfgs[0].timeout == 120  # MCS_TIMEOUT default, not overridden
    assert cfgs[0].rate_limit == 0  # MCS_RATE_LIMIT default, not overridden
    assert cfgs[1].api_key == "secret-2"
    assert cfgs[1].timeout == 30
    assert cfgs[1].rate_limit == 5


def test_missing_file_raises_oserror():
    with pytest.raises(OSError):
        load_providers("/nonexistent/path/providers.yaml")


def test_empty_providers_map_raises(tmp_path):
    path = _write(tmp_path, "providers: {}\n")
    with pytest.raises(ValueError, match="no providers defined"):
        load_providers(path)


def test_missing_required_field_names_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("CSCS_KEY", "secret")
    path = _write(
        tmp_path,
        """
        providers:
          cscs:
            api_key_env: CSCS_KEY
            model: swiss-ai/Apertus-8B
        """,
    )
    with pytest.raises(ValueError, match=r"'cscs'.*base_url"):
        load_providers(path)


def test_unset_api_key_env_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CSCS_KEY", raising=False)
    path = _write(
        tmp_path,
        """
        providers:
          cscs:
            base_url: https://cscs.example/v1
            api_key_env: CSCS_KEY
            model: swiss-ai/Apertus-8B
        """,
    )
    with pytest.raises(ValueError, match="CSCS_KEY"):
        load_providers(path)
