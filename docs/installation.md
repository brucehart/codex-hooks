# Installation and configuration

## Automated installation

From the repository root:

```bash
./scripts/install.sh
source ~/.bashrc
```

The installer is idempotent. It copies the estimator into the user Codex
configuration directory, merges a `SessionEnd` group into `hooks.json`, writes
the Bash wrapper as a separate generated file, and adds a small managed source
block to `.bashrc`.

Use non-default paths when testing an isolated configuration:

```bash
./scripts/install.sh \
  --codex-home /tmp/codex-home \
  --bashrc /tmp/test-bashrc \
  --config-dir /tmp/codex-hooks-config \
  --spool-dir /tmp/codex-hooks-cache
```

## Hook configuration

The generated hook group is equivalent to:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.codex/hooks/api-cost/codex_api_cost.py --spool-dir ~/.cache/codex-hooks/api-cost",
            "timeout": 3
          }
        ]
      }
    ]
  }
}
```

The actual generated command uses absolute paths. `SessionEnd` has a maximum
three-second timeout, so the estimator performs only local, streaming JSONL
parsing. When an OpenRouter model is used, it fetches public pricing from
OpenRouter's official models endpoint and caches it for 24 hours.

## Hook trust

Codex requires review of new or changed non-managed command hooks. Open Codex,
run `/hooks`, inspect the source and command, and trust it. Trust is based on
the hook definition; changing the configured command may require another
review.

## Shell activation

The terminal wrapper must be loaded in every shell that launches Codex:

```bash
source ~/.bashrc
type codex
```

If `type codex` reports only a filesystem path, that shell has not loaded the
wrapper. This commonly looks folder-specific when different folders are open
in long-lived terminal tabs.

Commands that invoke an absolute Codex executable path bypass the wrapper.
Normal aliases such as `alias codex-yolo='codex ...'` use it.

## Manual estimator check

The hook consumes the JSON object Codex writes to hook stdin. For diagnostics,
you can point it at a transcript and print immediately:

```bash
printf '%s\n' '{
  "session_id": "manual-test",
  "transcript_path": "/path/to/rollout.jsonl",
  "model": "gpt-5.6-sol"
}' | python3 src/codex_api_cost.py --stdout
```
