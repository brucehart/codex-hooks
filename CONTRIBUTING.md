# Contributing

Contributions are welcome, particularly for new public model rates, transcript
schema changes, shell portability, and test fixtures that do not contain
private conversation content.

## Development workflow

1. Create a focused branch.
2. Update code and documentation together.
3. Run:

   ```bash
   python3 -m unittest discover -s tests -v
   python3 -m py_compile src/codex_api_cost.py scripts/install.py
   bash -n scripts/install.sh
   ```

4. Never commit real Codex transcripts. Create minimal synthetic JSONL events
   for tests.
5. Cite the official OpenAI pricing page when changing rate tables and update
   `PRICING_UPDATED`.

Please keep the hook dependency-free and fast enough for the three-second
`SessionEnd` limit.
