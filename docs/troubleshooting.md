# Troubleshooting

## The hook appears briefly and disappears

The estimator is being run directly against the terminal instead of through
the deferred wrapper. Reinstall the current version, reload Bash, and verify
command resolution:

```bash
./scripts/install.sh
source ~/.bashrc
type codex
```

`type codex` must report a function.

## It works in one folder but not another

The hook is user-level and not tied to a folder. This symptom almost always
means the folders are open in different terminal tabs and only one tab has
reloaded `.bashrc`.

Run this in every already-open terminal:

```bash
source ~/.bashrc
type codex
```

New terminals load the wrapper automatically.

## No cost appears

Check the layers in order:

1. Run `/hooks` and confirm the user-level `SessionEnd` hook is enabled and
   trusted.
2. Confirm `type codex` reports a function.
3. Check for deferred output:

   ```bash
   find ~/.cache/codex-hooks/api-cost -maxdepth 1 -type f -print
   ```

4. Verify that `~/.codex/hooks.json` contains the installed absolute command.
5. Run the manual estimator check from the installation guide.

If a `session-*.txt` file exists after Codex exits, the hook worked but the
shell wrapper was bypassed. Avoid invoking the Codex binary by absolute path.

## Codex reports that the hook needs review

Run `/hooks`, inspect the command, and trust it. Reinstalling to a different
path or changing the command invalidates the previous definition's trust.

## The model has no estimate

Only models with an explicit public rate are calculated. The output names the
unsupported model and service tier. Add a rate only when it appears on the
official pricing page; aliases and private-looking model slugs should not be
guessed.

## The estimate differs from an API invoice

The output covers model tokens only. It excludes tool calls, storage,
containers, regional uplifts, and any pricing changes after the checked-in
snapshot. It is intended for capability-test comparisons, not billing
reconciliation.
