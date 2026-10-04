# Codex API Cost Hook

Print an estimated API-equivalent token cost after a Codex CLI session closes.

```text
Token usage: total=1,096,321 input=1,087,759 cached=977,664 output=8,562

API-equivalent token cost: $1.7318 (gpt-5.6-sol; token usage only)
```

Codex already records token usage in its local session transcript. This project
adds a user-level `SessionEnd` hook that reads those counters, applies current
OpenAI API token rates, plus live public rates for OpenRouter models, and defers
the result until after the terminal UI has fully exited.

## Why output is deferred

`SessionEnd` runs before Codex finishes restoring the terminal and printing its
own closing summary. Writing directly to `/dev/tty` therefore flashes briefly
and is overwritten. The installer adds two cooperating pieces:

1. A `SessionEnd` hook calculates the estimate and writes a per-session spool
   file.
2. A small Bash wrapper launches the real `codex` command and prints the new
   spool file only after the process exits.

This preserves Codex's exit code and accepts all normal Codex arguments.

## Requirements

- Codex CLI with lifecycle hook support
- Python 3.10 or newer
- Bash
- Linux, macOS, or WSL

## Install

```bash
git clone https://github.com/brucehart/codex-hooks.git
cd codex-hooks
./scripts/install.sh
source ~/.bashrc
```

Start Codex and run `/hooks` once. Review and trust the new user-level hook if
Codex prompts you to do so.

Confirm that the wrapper is active:

```bash
type codex
```

The result should begin with `codex is a function`. Existing terminals must
source `~/.bashrc` once; new terminals load the wrapper automatically.

## What gets installed

| Path | Purpose |
| --- | --- |
| `~/.codex/hooks/api-cost/codex_api_cost.py` | Session cost estimator |
| `~/.codex/hooks.json` | User-level `SessionEnd` hook registration |
| `~/.config/codex-hooks/api-cost.bash` | Deferred-output Bash wrapper |
| `~/.cache/codex-hooks/api-cost/` | Short-lived per-session output files |

The installer preserves existing hook groups and writes
`~/.codex/hooks.json.bak` before changing an existing hook file. Re-running the
installer updates this hook without adding a duplicate.

## Cost calculation

For models with cache-write pricing, the estimator uses:

```text
((input - cached - cache_write) × input_rate
 + cached × cached_rate
 + cache_write × cache_write_rate
 + output × output_rate) / 1,000,000
```

For other models, cache-write tokens remain part of ordinary input. Reasoning
tokens are not added separately because they are already included in the
reported output-token total.

OpenRouter model prices are fetched from its official `/api/v1/models` endpoint
and cached for 24 hours. OpenRouter publishes those rates per token; the hook
converts them to the same per-million-token units used by the built-in tables.

The parser follows model and service-tier changes across the transcript and
deduplicates repeated cumulative token events. Fast/priority, Flex, cache
writes, and long-context rate bands are supported where public rates exist.

## Important limitations

- This is a counterfactual API token estimate, not a ChatGPT or Codex charge.
- It excludes separately billed tools such as web search, file search, and
  hosted containers.
- Regional-processing uplifts are not applied.
- Models without a public API price are reported as unavailable instead of
  being assigned a guessed rate.
- Codex documents the local transcript as a convenience rather than a stable
  hook interface, so future CLI releases may require parser updates.
- Built-in OpenAI prices are a checked-in snapshot last updated **2026-09-29**,
  including GPT-6.1 Sol Standard, Fast, and Flex rates for both context bands.
  OpenRouter prices are refreshed daily. Compare both with their official
  pricing sources before using estimates for budgeting.

## Documentation

- [Installation and configuration](docs/installation.md)
- [Design and data flow](docs/design.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Contributing](CONTRIBUTING.md)

Codex hook behavior is documented in the official [Codex hooks guide][hooks].

## Development

Run the test suite and syntax checks:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile src/codex_api_cost.py scripts/install.py
bash -n scripts/install.sh
```

## License

[MIT](LICENSE)

[hooks]: https://learn.chatgpt.com/docs/hooks#sessionend
[pricing]: https://developers.openai.com/api/docs/pricing
