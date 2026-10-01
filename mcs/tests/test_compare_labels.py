"""Unit tests for mcs.capabilities' provider-aware compare table (SPEC.md
§13): column labels/headers must use the provider name when set, and fall
back to the model id (byte-identical to pre-§13 output) otherwise. Mocks
run_checks so no network call happens."""

from mcs import capabilities
from mcs.capabilities import PASS, Result
from mcs.config import Config


def _cfg(model, api_base="https://x/v1", label=""):
    return Config(
        api_base=api_base,
        api_key="k",
        model=model,
        timeout=1,
        rate_limit=0,
        label=label,
    )


def test_same_base_uses_model_id_labels(monkeypatch, capsys):
    monkeypatch.setattr(
        capabilities,
        "run_checks",
        lambda c, capability, spec: [Result("check_a", PASS)],
    )
    configs = [_cfg("model-a"), _cfg("model-b")]

    code = capabilities.report_compare(configs)

    out = capsys.readouterr().out
    assert code == 0
    assert "Capability comparison (https://x/v1)" in out
    assert "M1 = model-a" in out
    assert "M2 = model-b" in out


def test_different_base_uses_provider_labels(monkeypatch, capsys):
    def fake_run_checks(config, capability, spec):
        status = PASS if config.label == "cscs" else capabilities.FAIL
        return [Result("check_a", status)]

    monkeypatch.setattr(capabilities, "run_checks", fake_run_checks)
    configs = [
        _cfg("model-a", api_base="https://cscs/v1", label="cscs"),
        _cfg("model-b", api_base="https://rcp/v1", label="rcp"),
    ]

    code = capabilities.report_compare(configs)

    out = capsys.readouterr().out
    assert code == 1  # rcp's failure makes the whole run non-zero
    assert "Capability comparison across 2 providers" in out
    assert "M1 = cscs — https://cscs/v1 — model model-a" in out
    assert "M2 = rcp — https://rcp/v1 — model model-b" in out


def test_json_output_includes_providers_and_null_api_base_when_mixed(monkeypatch):
    monkeypatch.setattr(
        capabilities,
        "run_checks",
        lambda c, capability, spec: [Result("check_a", PASS)],
    )
    configs = [
        _cfg("model-a", api_base="https://cscs/v1", label="cscs"),
        _cfg("model-b", api_base="https://rcp/v1", label="rcp"),
    ]

    import io
    import json
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        code = capabilities.report_compare(configs, as_json=True)

    data = json.loads(buf.getvalue())
    assert code == 0
    assert data["api_base"] is None
    assert [p["label"] for p in data["providers"]] == ["cscs", "rcp"]


def test_report_shows_provider_label_in_title(monkeypatch, capsys):
    monkeypatch.setattr(
        capabilities,
        "run_checks",
        lambda config, capability, spec, junit: [Result("check_a", PASS)],
    )
    config = _cfg("model-a", api_base="https://cscs/v1", label="cscs")

    capabilities.report(config)

    out = capsys.readouterr().out
    assert "Capability checks for model-a  (provider: cscs)" in out
