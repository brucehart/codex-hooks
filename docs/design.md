# Design and data flow

## Lifecycle

```text
interactive shell
    │
    ├─ creates a start-time marker
    │
    └─ launches the real Codex CLI
            │
            ├─ records cumulative token_count events in rollout JSONL
            │
            └─ fires SessionEnd
                    │
                    └─ estimator writes session-<id>.txt
            │
            └─ restores terminal and prints its normal closing summary
    │
    └─ wrapper finds output newer than its marker and prints it
```

Separating calculation from display is deliberate. Hook stdout is owned by
Codex, and direct terminal writes happen too early in shutdown. A spool file is
simple, local, and independent of environment-variable inheritance; Codex may
sanitize the environment of hook commands.

## Transcript parsing

The estimator processes the transcript line by line to stay within the short
`SessionEnd` timeout and avoid holding chat content in memory. It reads only:

- `turn_context.payload.model`
- `turn_context.payload.service_tier`
- `event_msg` records whose payload type is `token_count`
- `total_token_usage` input, cached-input, cache-write, and output counters

Token counters are cumulative. The parser subtracts the previous total to
recover per-request usage and ignores repeated totals. Per-request deltas are
necessary because pricing can change when the model, service tier, or context
band changes during a session.

## Pricing policy

Rates are checked into the estimator so shutdown does not depend on network
availability. The code intentionally reports unsupported public or private
model slugs instead of guessing a mapping.

When updating rates:

1. Use the official OpenAI API pricing page.
2. Update Standard, Fast, and Flex tables independently.
3. Change `PRICING_UPDATED`.
4. Add or update rate-specific unit tests.
5. Note any unsupported service-tier or long-context combinations.

## Concurrency

Each wrapper invocation creates a unique marker. The hook writes a file keyed
by the Codex session ID. After Codex exits, the wrapper prints the newest
session file created after its marker and then removes both files. This handles
normal parallel terminal usage without using process-specific environment
variables inside the hook.
