from __future__ import annotations

import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


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
    def test_request_cost_accounts_for_cache_reads_and_writes(self) -> None:
        usage = {
            "input_tokens": 1_000,
            "cached_input_tokens": 400,
            "cache_write_input_tokens": 100,
            "output_tokens": 10,
        }
        prices = codex_api_cost.STANDARD["gpt-5.6-sol"]["short"]
        self.assertEqual(codex_api_cost.request_cost(usage, prices), Decimal("0.003625"))

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

        self.assertEqual(result.cost, Decimal("0.007250"))
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
