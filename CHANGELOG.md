# Changelog

## Unreleased

- Replaced the overview's balance totals with matched start and end balance observations for approved private holders, with explicit coverage and a separate last-operation timestamp.

- Added a six-minute GitHub Actions continuation timer and a data freshness check for automatic scans.
- Added the manual Telegram delivery test and grouped alerts that show balances, approximate USD amounts, and 7- and 30-day direct XLM flows.
- Separated approved private holders from unreviewed candidates and service wallets in the dashboard and Telegram.
- Added resumable Horizon payment backfills and accumulation rankings for 1, 7, and 30 completed UTC days.
- Added current XLM/USD equivalents across the site and per-wallet asset valuations with explicit quote coverage.

## 0.3.2

- Optional Telegram digest with secret-based setup and delivery checkpoint.
- Freshness guard for backup dispatches, with separate reporting for successful fallback scans.

## 0.3.1

- Daily Coinbase Exchange XLM/USD closes aligned with UTC wallet balance changes.
- Wallet inactivity based on scanned operations, a dormant filter, and activity-resumption alerts.
- Repeated direct XLM transfers with transaction evidence and no ownership inference.

## 0.3.0

- UTC daily balance changes and complete-window rankings for 7 and 30 days.
- Per-wallet statistical balance alerts, with minimum history and stable event identifiers.
- Published status distinguishes successful scheduled scans from other triggers.

## 0.2.0

- Exchange wallet registry, observed native XLM flows, balance history and large exchange alerts.
- Confirmed Stellar DEX executions, separate cursor, exact per-pair volumes and initiator-side classification.
- Market views in GitHub Pages and versioned minute aggregates.

## 0.1.0

- Horizon Mainnet ingestion, resumable paging cursor, exact amounts, crash-safe history and compact static export.
- Russian dashboard, holder and wallet views, paged large operations and basic anomalies.
- Browser-local watchlist, data refresh and GitHub Actions Pages workflow.
- Centralized exchange flows and confirmed DEX trades remain planned for v0.2.
