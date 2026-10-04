from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import codex_api_cost  # noqa: E402


def token_event(input_tokens: int, cached: int, writes: int, output: int) -> dict:
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached,
                    "cache_write_input_tokens": writes,
                    "output_tokens": output,
                }
            },
        },
    }


class CostTests(unittest.TestCase):
    def test_gpt_61_sol_estimates_tiers_and_context_boundary(self) -> None:
        # Includes 400 cache reads, 100 cache writes, and 10 output tokens.
        # At 272K input tokens the short rates still apply.
        cases = [(1_000, "0.00139"), (272_000, "0.54339"), (272_001, "1.086734")]
        for tier, multiplier in [(None, "1"), ("fast", "2"), ("priority", "2"), ("flex", ".5")]:
            for input_tokens, standard_cost in cases:
                with self.subTest(tier=tier, input_tokens=input_tokens):
                    with tempfile.TemporaryDirectory() as directory:
                        transcript = Path(directory) / "rollout.jsonl"
                        rows = [
                            {
                                "type": "turn_context",
                                "payload": {"model": "gpt-6.1-sol", "service_tier": tier},
                            },
                            token_event(input_tokens, 400, 100, 10),
                        ]
                        transcript.write_text(
                            "".join(json.dumps(row) + "\n" for row in rows),
                            encoding="utf-8",
                        )
                        result = codex_api_cost.estimate(transcript, "fallback")

                    self.assertEqual(result.cost, Decimal(standard_cost) * Decimal(multiplier))
                    self.assertEqual(result.models, {"gpt-6.1-sol"})
                    self.assertEqual(result.unsupported, set())

    def test_current_flagship_rates_match_official_pricing(self) -> None:
        expected = {
            "standard": {
                "gpt-6-astra": {
                    "short": ("10", "1", "12.5", "50"),
                    "long": ("20", "2", "25", "75"),
                },
                "gpt-6-luna": {
                    "short": (".1", ".01", ".125", ".5"),
                    "long": (".2", ".02", ".25", ".75"),
                },
                "gpt-5.6-sol": {
                    "short": ("4", ".4", "5", "20"),
                    "long": ("8", ".8", "10", "30"),
                },
                "gpt-5.6-terra": {
                    "short": ("2", ".2", "2.5", "12"),
                    "long": ("4", ".4", "5", "18"),
                },
                "gpt-5.6-luna": {
                    "short": (".2", ".02", ".25", "1.2"),
                    "long": (".4", ".04", ".5", "1.8"),
                },
                "gpt-5.6-cyber": {
                    "short": ("12.5", "1.25", "15.625", "75"),
                },
            },
            "fast": {
                "gpt-6-astra": {
                    "short": ("20", "2", "25", "100"),
                    "long": ("40", "4", "50", "150"),
                },
                "gpt-6-luna": {
                    "short": (".2", ".02", ".25", "1"),
                    "long": (".4", ".04", ".5", "1.5"),
                },
                "gpt-5.6-sol": {
                    "short": ("8", ".8", "10", "40"),
                    "long": ("16", "1.6", "20", "60"),
                },
                "gpt-5.6-terra": {
                    "short": ("4", ".4", "5", "24"),
                    "long": ("8", ".8", "10", "36"),
                },
                "gpt-5.6-luna": {
                    "short": (".4", ".04", ".5", "2.4"),
                    "long": (".8", ".08", "1", "3.6"),
                },
                "gpt-5.6-cyber": {
                    "short": ("25", "2.5", "31.25", "150"),
                },
            },
            "flex": {
                "gpt-6-astra": {
                    "short": ("5", ".5", "6.25", "25"),
                    "long": ("10", "1", "12.5", "37.5"),
                },
                "gpt-6-luna": {
                    "short": (".05", ".005", ".0625", ".25"),
                    "long": (".1", ".01", ".125", ".375"),
                },
                "gpt-5.6-sol": {
                    "short": ("2", ".2", "2.5", "10"),
                    "long": ("4", ".4", "5", "15"),
                },
                "gpt-5.6-terra": {
                    "short": ("1", ".1", "1.25", "6"),
                    "long": ("2", ".2", "2.5", "9"),
                },
                "gpt-5.6-luna": {
                    "short": (".1", ".01", ".125", ".6"),
                    "long": (".2", ".02", ".25", ".9"),
                },
                "gpt-5.6-cyber": {
                    "short": ("6.25", ".625", "7.8125", "37.5"),
                },
            },
        }

        for tier, models in expected.items():
            for model, bands in models.items():
                for band, values in bands.items():
                    with self.subTest(tier=tier, model=model, band=band):
                        self.assertEqual(
                            codex_api_cost.RATES[tier][model][band],
                            codex_api_cost.Rate(*(Decimal(value) for value in values)),
                        )

    def test_openrouter_prices_are_converted_from_per_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory) / "models.json"
            cache.write_text(
                json.dumps(
                    {
                        "fetched_at": 9_999_999_999,
                        "models": [
                            {
                                "id": "deepseek/example",
                                "pricing": {
                                    "prompt": "0.00000009",
                                    "completion": "0.00000018",
                                    "input_cache_read": "0.000000018",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(codex_api_cost, "OPENROUTER_CACHE", cache):
                prices = codex_api_cost.load_openrouter_models()["deepseek/example"]

        self.assertEqual(prices.input, Decimal("0.09"))
        self.assertEqual(prices.cached_input, Decimal("0.018"))
        self.assertEqual(prices.output, Decimal("0.18"))

    def test_request_cost_accounts_for_cache_reads_and_writes(self) -> None:
        usage = {
            "input_tokens": 1_000,
            "cached_input_tokens": 400,
            "cache_write_input_tokens": 100,
            "output_tokens": 10,
        }
        prices = codex_api_cost.STANDARD["gpt-5.6-sol"]["short"]
        self.assertEqual(codex_api_cost.request_cost(usage, prices), Decimal("0.00286"))

    def test_estimate_deduplicates_repeated_totals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "rollout.jsonl"
            rows = [
                {
                    "type": "turn_context",
                    "payload": {
                        "model": "gpt-5.6-sol",
                        "service_tier": None,
                    },
                },
                token_event(1_000, 400, 100, 10),
                token_event(1_000, 400, 100, 10),
                token_event(2_000, 800, 200, 20),
            ]
            transcript.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            result = codex_api_cost.estimate(transcript, "fallback")

        self.assertEqual(result.cost, Decimal("0.00572"))
        self.assertEqual(result.models, {"gpt-5.6-sol"})
        self.assertEqual(result.unsupported, set())

    def test_unknown_model_is_reported_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "rollout.jsonl"
            transcript.write_text(
                json.dumps(token_event(100, 0, 0, 10)) + "\n",
                encoding="utf-8",
            )
            result = codex_api_cost.estimate(transcript, "private-model")

        self.assertEqual(result.cost, Decimal(0))
        self.assertEqual(result.unsupported, {"private-model/standard"})
        self.assertIn("unavailable", codex_api_cost.format_estimate(result, "private-model"))

    def test_spool_message_sanitizes_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = codex_api_cost.spool_message(
                Path(directory),
                "session/../../unsafe",
                "cost",
            )
            self.assertEqual(output.parent, Path(directory))
            self.assertEqual(output.read_text(encoding="utf-8"), "cost\n")
            self.assertNotIn("/", output.name)


if __name__ == "__main__":
    unittest.main()
