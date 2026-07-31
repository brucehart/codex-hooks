# Security policy

## Reporting a vulnerability

Please report security concerns privately through GitHub's security-advisory
interface rather than opening a public issue.

## Data handling

The hook processes Codex transcripts locally and does not send their contents
over the network. It reads token counters, model names, and service-tier values.
Deferred output files contain only the formatted cost estimate.

The installer modifies user-level Codex and Bash configuration. Review
`scripts/install.py` and the generated hook in `/hooks` before trusting it.
