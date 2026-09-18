"""`mcs` console entrypoint.

Runs the deterministic suites against a served model and prints a capability
table (✔/✗/⚠ per check), exiting non-zero on any failure. Scope to one
capability with `--capability TYPE`, compare models with repeated `--model`,
or compare across different providers/endpoints with `--providers-config`
(SPEC.md §13; mutually exclusive with --base-url/--model/--rate-limit).
See SPEC.md sections 3, 8, and 13.
"""

import argparse
import os
import sys

_CAPABILITIES = [
    "core",
    "special_tokens",
    "streaming",
    "tools",
    "multimodal",
    "multiturn",
    "reasoning",
    "robustness",
    "perf",
]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(prog="mcs")
    p.add_argument(
        "--capability",
        "--suite",
        dest="capability",
        help="run only this capability, e.g. tools (comma-separated ok; default: all)",
    )
    p.add_argument(
        "--model",
        action="append",
        help="model id; repeat for a multi-model comparison table",
    )
    p.add_argument("--base-url")
    p.add_argument(
        "--providers-config",
        metavar="PATH",
        dest="providers_config",
        help="YAML file of named providers (base_url/api_key_env/model each) "
        "to compare across different endpoints, e.g. CSCS vs RCP (SPEC.md "
        "§13). Runs every provider listed in the file -- put only the ones "
        "you want compared in it. Mutually exclusive with --base-url/"
        "--model/--rate-limit and their MCS_* env equivalents.",
    )
    p.add_argument(
        "--rate-limit",
        dest="rate_limit",
        type=float,
        metavar="N",
        help="max requests per minute sent to the endpoint, e.g. 10 "
        "(default: unrestricted)",
    )
    p.add_argument("--junit", metavar="PATH", help="also write JUnit XML here")
    p.add_argument("--json", action="store_true", help="emit the result as JSON")
    p.add_argument(
        "--detail",
        action="store_true",
        help="in a multi-model comparison, list the failure reasons",
    )
    p.add_argument(
        "--spec",
        type=str.lower,
        choices=["openai", "dev"],
        default="openai",
        help="API surface to test: 'openai' (default) runs only checks the "
        "OpenAI API spec can serve; 'dev' adds checks that need extension "
        "endpoints like /tokenize and /detokenize",
    )
    p.add_argument(
        "--record-responses",
        metavar="DIR",
        dest="record_dir",
        help="record each test's request + response under "
        "DIR/<test-name>/<model>_input.txt and _output.txt",
    )
    args = p.parse_args(argv)

    if args.providers_config:
        # Strict mode split (SPEC.md §13): args/env-var mode and
        # --providers-config are mutually exclusive, never silently merged.
        # Detected at the flag/env layer (not via Config.from_env(), whose
        # resolved values are indistinguishable from its own defaults).
        conflicts = []
        if args.base_url or os.environ.get("MCS_API_BASE"):
            conflicts.append("--base-url/MCS_API_BASE")
        if args.model or os.environ.get("MCS_MODEL"):
            conflicts.append("--model/MCS_MODEL")
        if args.rate_limit is not None or os.environ.get("MCS_RATE_LIMIT"):
            conflicts.append("--rate-limit/MCS_RATE_LIMIT")
        if os.environ.get("MCS_TIMEOUT"):
            conflicts.append("MCS_TIMEOUT")
        if conflicts:
            p.error(
                "--providers-config cannot be combined with "
                f"{', '.join(conflicts)} -- use one mode or the other, not both"
            )

    models = args.model or []
    if len(models) == 1:
        os.environ["MCS_MODEL"] = models[0]
    if args.base_url:
        os.environ["MCS_API_BASE"] = args.base_url
    if args.rate_limit is not None:
        os.environ["MCS_RATE_LIMIT"] = str(args.rate_limit)
    if args.record_dir:
        if os.path.exists(args.record_dir):
            p.error(
                f"--record-responses directory already exists: {args.record_dir} "
                f"(refusing to overwrite; choose a new path or remove it)"
            )
        os.environ["MCS_RECORD_DIR"] = os.path.abspath(args.record_dir)

    cap = None
    if args.capability:
        wanted = [s.strip() for s in args.capability.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in _CAPABILITIES]
        if unknown:
            p.error(
                f"unknown capability: {', '.join(unknown)} "
                f"(choose from: {', '.join(_CAPABILITIES)})"
            )
        cap = " or ".join(wanted)

    import dataclasses

    from .capabilities import report, report_compare
    from .config import Config, load_providers

    if args.providers_config:
        try:
            cfgs = load_providers(args.providers_config)
        except (OSError, ValueError) as e:
            p.error(str(e))
        if len(cfgs) == 1:
            return report(
                cfgs[0],
                capability=cap,
                spec=args.spec,
                as_json=args.json,
                junit=args.junit,
            )
        return report_compare(
            cfgs, capability=cap, spec=args.spec, as_json=args.json, detail=args.detail
        )

    base = Config.from_env()
    if not base.api_key:
        p.error("no API key (set SWISSAI_RESEARCH_API_KEY or MCS_API_KEY)")

    if len(models) > 1:
        cfgs = [dataclasses.replace(base, model=m) for m in models]
        return report_compare(
            cfgs, capability=cap, spec=args.spec, as_json=args.json, detail=args.detail
        )
    return report(
        base, capability=cap, spec=args.spec, as_json=args.json, junit=args.junit
    )


if __name__ == "__main__":
    raise SystemExit(main())
