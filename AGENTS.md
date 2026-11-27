# XLM Radar

- Keep the public data contract versioned and document compatible schema changes in README.md and CHANGELOG.md.
- Keep collection, storage, analytics, export and individual UI sections independent. Use the shared UI module for tables, formatting and safe links.
- Use integer stroops for ledger amounts, UTC timestamps and stable event IDs. Never delete history or advance a cursor over failed or unprocessed records.
- Keep credentials out of files, logs and public artifacts. Publish only dist/ through GitHub Pages and use scoped GitHub Actions permissions.
- Run `python3 -m unittest discover -s tests -v` and `python3 -m collector.export`. Check desktop and a 320 px viewport for interface changes.
- Distinguish observed transfers, net balance changes and confirmed trades. Preserve sources and confidence for known labels. Mark incomplete periods and planned modules.
