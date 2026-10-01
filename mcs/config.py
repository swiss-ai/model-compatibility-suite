"""Runtime configuration, resolved from environment variables.

See SPEC.md section 3 for the full table. Flags handled by run.sh / cli.py are
exported into these same env vars before pytest runs, so this is the single
source of truth.
"""

import os
import sys
from dataclasses import dataclass


def _env(*names, default=None):
    """Return the first set, non-empty environment variable among names."""
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return default


_warned_deprecated_key = False


def _api_key() -> str:
    """Bearer token: MCS_API_KEY, then SWISSAI_RESEARCH_API_KEY. The old
    CSCS_SERVING_API name still works but warns (once) that it's deprecated."""
    global _warned_deprecated_key
    key = _env("MCS_API_KEY", "SWISSAI_RESEARCH_API_KEY")
    if key:
        return key
    key = _env("CSCS_SERVING_API", default="")
    if key and not _warned_deprecated_key:
        _warned_deprecated_key = True
        print(
            "warning: CSCS_SERVING_API is deprecated; "
            "set SWISSAI_RESEARCH_API_KEY instead",
            file=sys.stderr,
        )
    return key


@dataclass(frozen=True)
class Config:
    api_base: str
    api_key: str
    model: str
    timeout: float
    rate_limit: float
    # Provider name from a --providers-config entry (SPEC.md §13); "" for the
    # plain args/env-var mode. Used only for display (compare-table columns,
    # recording filenames) -- never affects request behavior.
    label: str = ""

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_base=_env(
                "MCS_API_BASE", default="https://api.swissai.svc.cscs.ch/v1"
            ).rstrip("/"),
            api_key=_api_key(),
            model=_env(
                "MCS_MODEL", default="CSCS-Inference/swiss-ai/Apertus-8B-Instruct-2509"
            ),
            timeout=float(_env("MCS_TIMEOUT", default="120")),
            # Requests per MINUTE; 0 = unrestricted (the default). Some serving
            # endpoints cap at 15 req/min per user -- pass --rate-limit (or set
            # MCS_RATE_LIMIT) to stay under such caps.
            rate_limit=float(_env("MCS_RATE_LIMIT", default="0")),
        )


def load_providers(path: str) -> list:
    """Load every named provider from a YAML file (SPEC.md §13) into Configs.

    Each entry under `providers:` needs `base_url`, `api_key_env` (the NAME of
    an env var holding the bearer token -- never the raw key in the file), and
    `model`; `timeout`/`rate_limit` are optional per-provider overrides,
    falling back to MCS_TIMEOUT/MCS_RATE_LIMIT (§3) when omitted.

    Runs every provider in the file, in file order -- there is no separate
    "pick a subset" flag. The file itself is the selection: put only the
    providers you want compared in a given run in it. Raises ValueError on
    any missing/unresolved field, naming the offending provider -- fail
    loudly, no silent skips (§8).
    """
    import yaml

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    providers = data.get("providers") or {}
    if not providers:
        raise ValueError(
            f"no providers defined in {path} (expected a 'providers:' map)"
        )

    configs = []
    for name in providers:
        entry = providers[name] or {}
        missing = [k for k in ("base_url", "api_key_env", "model") if not entry.get(k)]
        if missing:
            raise ValueError(
                f"provider '{name}' in {path} is missing required field(s): "
                f"{', '.join(missing)}"
            )
        key_env = entry["api_key_env"]
        api_key = os.environ.get(key_env, "")
        if not api_key:
            raise ValueError(
                f"provider '{name}': env var {key_env} (its api_key_env) is not set"
            )
        configs.append(
            Config(
                api_base=str(entry["base_url"]).rstrip("/"),
                api_key=api_key,
                model=entry["model"],
                timeout=float(
                    entry.get("timeout") or _env("MCS_TIMEOUT", default="120")
                ),
                rate_limit=float(
                    entry.get("rate_limit") or _env("MCS_RATE_LIMIT", default="0")
                ),
                label=name,
            )
        )
    return configs
