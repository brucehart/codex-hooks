#!/usr/bin/env python3
"""Estimate API-equivalent token cost from a Codex session transcript."""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple


MILLION = Decimal("1000000")
LONG_CONTEXT_THRESHOLD = 272_000
PRICING_UPDATED = "2026-07-30"


class Rate(NamedTuple):
    input: Decimal
    cached_input: Decimal
    cache_write: Decimal | None
    output: Decimal


class Estimate(NamedTuple):
    cost: Decimal
    models: set[str]
    unsupported: set[str]


def rate(input_: str, cached: str, output: str, write: str | None = None) -> Rate:
    return Rate(
        Decimal(input_),
        Decimal(cached),
        Decimal(write) if write is not None else None,
        Decimal(output),
    )


# USD per 1M tokens. Source: https://developers.openai.com/api/docs/pricing
# "short" applies to requests with at most 272K input tokens.
STANDARD: dict[str, dict[str, Rate]] = {
    "gpt-5.6-sol": {
        "short": rate("5", ".5", "30", "6.25"),
        "long": rate("10", "1", "45", "12.5"),
    },
    "gpt-5.6-terra": {
        "short": rate("2", ".2", "12", "2.5"),
        "long": rate("4", ".4", "18", "5"),
    },
    "gpt-5.6-luna": {
        "short": rate(".2", ".02", "1.2", ".25"),
        "long": rate(".4", ".04", "1.8", ".5"),
    },
    "gpt-5.5": {
        "short": rate("5", ".5", "30"),
        "long": rate("10", "1", "45"),
    },
    "gpt-5.4": {
        "short": rate("2.5", ".25", "15"),
        "long": rate("5", ".5", "22.5"),
    },
    "gpt-5.4-mini": {"short": rate(".75", ".075", "4.5")},
    "gpt-5.4-nano": {"short": rate(".2", ".02", "1.25")},
    "gpt-5.2": {"short": rate("1.75", ".175", "14")},
    "gpt-5.1": {"short": rate("1.25", ".125", "10")},
    "gpt-5": {"short": rate("1.25", ".125", "10")},
    "gpt-5.3-codex": {"short": rate("1.75", ".175", "14")},
    "gpt-5.2-codex": {"short": rate("1.75", ".175", "14")},
    "gpt-5.1-codex-max": {"short": rate("1.25", ".125", "10")},
    "gpt-5.1-codex": {"short": rate("1.25", ".125", "10")},
    "gpt-5-codex": {"short": rate("1.25", ".125", "10")},
    "gpt-5.1-codex-mini": {"short": rate(".25", ".025", "2")},
    "codex-mini-latest": {"short": rate("1.5", ".375", "6")},
}

FAST: dict[str, dict[str, Rate]] = {
    "gpt-5.6-sol": {"short": rate("10", "1", "60", "12.5")},
    "gpt-5.6-terra": {"short": rate("4", ".4", "24", "5")},
    "gpt-5.6-luna": {"short": rate(".4", ".04", "2.4", ".5")},
    "gpt-5.5": {"short": rate("12.5", "1.25", "75")},
    "gpt-5.4": {"short": rate("5", ".5", "30")},
    "gpt-5.4-mini": {"short": rate("1.5", ".15", "9")},
    "gpt-5.2": {"short": rate("3.5", ".35", "28")},
    "gpt-5.1": {"short": rate("2.5", ".25", "20")},
    "gpt-5": {"short": rate("2.5", ".25", "20")},
    "gpt-5.3-codex": {"short": rate("3.5", ".35", "28")},
    "gpt-5.2-codex": {"short": rate("3.5", ".35", "28")},
    "gpt-5.1-codex-max": {"short": rate("2.5", ".25", "20")},
    "gpt-5.1-codex": {"short": rate("2.5", ".25", "20")},
    "gpt-5-codex": {"short": rate("2.5", ".25", "20")},
}

FLEX: dict[str, dict[str, Rate]] = {
    "gpt-5.6-sol": {
        "short": rate("2.5", ".25", "15", "3.125"),
        "long": rate("5", ".5", "22.5", "6.25"),
    },
    "gpt-5.6-terra": {
        "short": rate("1", ".1", "6", "1.25"),
        "long": rate("2", ".2", "9", "2.5"),
    },
    "gpt-5.6-luna": {
        "short": rate(".1", ".01", ".6", ".125"),
        "long": rate(".2", ".02", ".9", ".25"),
    },
    "gpt-5.5": {
        "short": rate("2.5", ".25", "15"),
        "long": rate("5", ".5", "22.5"),
    },
    "gpt-5.4": {
        "short": rate("1.25", ".13", "7.5"),
        "long": rate("2.5", ".25", "11.25"),
    },
    "gpt-5.4-mini": {"short": rate(".375", ".0375", "2.25")},
    "gpt-5.4-nano": {"short": rate(".1", ".01", ".625")},
    "gpt-5.2": {"short": rate(".875", ".0875", "7")},
    "gpt-5.1": {"short": rate(".625", ".0625", "5")},
    "gpt-5": {"short": rate(".625", ".0625", "5")},
}

RATES = {"standard": STANDARD, "fast": FAST, "flex": FLEX}
TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "output_tokens",
)


def normalize_tier(value: object) -> str:
    if value in ("fast", "priority"):
        return "fast"
    if value == "flex":
        return "flex"
    return "standard"


def token_values(usage: dict[str, object]) -> dict[str, int]:
    return {name: int(usage.get(name, 0) or 0) for name in TOKEN_FIELDS}


def delta_usage(current: dict[str, int], previous: dict[str, int] | None) -> dict[str, int]:
    if previous is None or any(current[name] < previous[name] for name in TOKEN_FIELDS):
        return current
    return {name: current[name] - previous[name] for name in TOKEN_FIELDS}


def request_cost(usage: dict[str, int], prices: Rate) -> Decimal:
    cached = usage["cached_input_tokens"]
    writes = usage["cache_write_input_tokens"]
    if prices.cache_write is None:
        uncached = max(0, usage["input_tokens"] - cached)
        write_cost = Decimal(0)
    else:
        uncached = max(0, usage["input_tokens"] - cached - writes)
        write_cost = Decimal(writes) * prices.cache_write

    return (
        Decimal(uncached) * prices.input
        + Decimal(cached) * prices.cached_input
        + write_cost
        + Decimal(usage["output_tokens"]) * prices.output
    ) / MILLION


def estimate(transcript: Path, fallback_model: str) -> Estimate:
    total_cost = Decimal(0)
    models_used: set[str] = set()
    unsupported: set[str] = set()
    current_model = fallback_model
    current_tier = "standard"
    previous_total: dict[str, int] | None = None

    with transcript.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue

            if item.get("type") == "turn_context":
                payload = item.get("payload") or {}
                current_model = str(payload.get("model") or current_model)
                current_tier = normalize_tier(payload.get("service_tier"))
                continue

            payload = item.get("payload") or {}
            if item.get("type") != "event_msg" or payload.get("type") != "token_count":
                continue

            info = payload.get("info") or {}
            raw_total = info.get("total_token_usage")
            if not isinstance(raw_total, dict):
                continue

            current_total = token_values(raw_total)
            usage = delta_usage(current_total, previous_total)
            previous_total = current_total
            if not any(usage.values()):
                continue

            models_used.add(current_model)
            model_rates = RATES[current_tier].get(current_model)
            if model_rates is None:
                unsupported.add(f"{current_model}/{current_tier}")
                continue

            band = "long" if usage["input_tokens"] > LONG_CONTEXT_THRESHOLD else "short"
            prices = model_rates.get(band)
            if prices is None:
                unsupported.add(f"{current_model}/{current_tier}/{band}")
                continue
            total_cost += request_cost(usage, prices)

    return Estimate(total_cost, models_used, unsupported)


def format_estimate(result: Estimate, fallback_model: str) -> str:
    model_label = ", ".join(sorted(result.models)) or fallback_model
    unsupported_label = ", ".join(sorted(result.unsupported))
    if result.unsupported and result.cost == 0:
        return (
            "API-equivalent token cost: unavailable "
            f"(no public price for {unsupported_label})"
        )
    if result.unsupported:
        return (
            f"API-equivalent token cost: at least ${result.cost:.4f} "
            f"({model_label}; no public price for {unsupported_label})"
        )
    return (
        f"API-equivalent token cost: ${result.cost:.4f} "
        f"({model_label}; token usage only)"
    )


def spool_message(output_dir: Path, session_id: str, message: str) -> Path:
    safe_session_id = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in session_id
    )
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    output_path = output_dir / f"session-{safe_session_id or 'unknown'}.txt"
    output_path.write_text(f"{message}\n", encoding="utf-8")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spool-dir",
        type=Path,
        default=Path.home() / ".cache" / "codex-hooks" / "api-cost",
        help="directory where the SessionEnd hook writes deferred output",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print immediately instead of writing a deferred output file",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        hook_input = json.load(sys.stdin)
        transcript_value = hook_input.get("transcript_path")
        fallback_model = str(hook_input.get("model") or "unknown")
        session_id = str(
            hook_input.get("session_id") or Path(transcript_value or "unknown").stem
        )
        if not transcript_value:
            return 0

        message = format_estimate(estimate(Path(transcript_value), fallback_model), fallback_model)
        if args.stdout:
            print(message, flush=True)
        else:
            spool_message(args.spool_dir, session_id, message)
        return 0
    except Exception as error:  # A close hook should never interfere with shutdown.
        print(f"API-equivalent token cost hook failed: {error}", file=sys.stderr, flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
