"""Unit tests for the --providers-config / args-mode strict split in mcs.cli
(SPEC.md §13). Only exercises the argument-validation paths (mcs.cli.main
exits via p.error() before any suite runs), so no network calls happen and no
API key is needed."""

import pytest

from mcs import cli


def test_providers_config_rejects_base_url(monkeypatch, tmp_path):
    monkeypatch.delenv("MCS_API_BASE", raising=False)
    path = tmp_path / "providers.yaml"
    path.write_text("providers: {}\n")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--providers-config", str(path), "--base-url", "https://x/v1"])
    assert excinfo.value.code == 2


def test_providers_config_rejects_model(monkeypatch, tmp_path):
    monkeypatch.delenv("MCS_MODEL", raising=False)
    path = tmp_path / "providers.yaml"
    path.write_text("providers: {}\n")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--providers-config", str(path), "--model", "some-model"])
    assert excinfo.value.code == 2


def test_providers_config_rejects_rate_limit(monkeypatch, tmp_path):
    path = tmp_path / "providers.yaml"
    path.write_text("providers: {}\n")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--providers-config", str(path), "--rate-limit", "10"])
    assert excinfo.value.code == 2


def test_providers_config_rejects_explicit_env_base(monkeypatch, tmp_path):
    monkeypatch.setenv("MCS_API_BASE", "https://x/v1")
    path = tmp_path / "providers.yaml"
    path.write_text("providers: {}\n")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--providers-config", str(path)])
    assert excinfo.value.code == 2


def test_providers_config_missing_file_errors_cleanly(monkeypatch):
    monkeypatch.delenv("MCS_API_BASE", raising=False)
    monkeypatch.delenv("MCS_MODEL", raising=False)
    monkeypatch.delenv("MCS_RATE_LIMIT", raising=False)
    monkeypatch.delenv("MCS_TIMEOUT", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--providers-config", "/nonexistent/providers.yaml"])
    assert excinfo.value.code == 2
