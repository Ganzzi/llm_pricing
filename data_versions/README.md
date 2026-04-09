# Data Versions Snapshots

This directory contains versioned snapshots of LLM pricing data.

## Purpose

- **Reference Data**: These snapshots are committed to git as the authoritative reference pricing data
- **Team Collaboration**: Snapshots ensure all team members use the same pricing data
- **Version History**: Multiple snapshots allow tracking pricing changes over time

## Filename Format

Snapshots follow the format: `YYYY-MM-DD_HHMMSS_ffffff.json`

- `YYYY-MM-DD`: Date
- `HHMMSS`: Time (hours, minutes, seconds)
- `ffffff`: Microseconds
- `.json`: JSON file extension

Example: `2025-12-03_105648_993360.json`

## Usage

Snapshots are automatically loaded when the package initializes:

1. If `data.json` doesn't exist in the project root, the latest snapshot is loaded
2. Once loaded, data persists in `data.json` (git-ignored) for local modifications
3. New snapshots can be created via `LLMPricing().store_snapshot()`

## Adding New Snapshots

```python
from llm_pricing import LLMPricing

pricing = LLMPricing()
# ... make changes ...
info = pricing.store_snapshot()
# Commit the new snapshot file to git
```

## Do NOT Modify

Do not manually edit snapshot files. They are generated programmatically to ensure data integrity.

## Local Data vs Snapshots

- **`data.json`**: Local working data (git-ignored, modified by user)
- **`data_versions/*.json`**: Reference snapshots (git-tracked, read-only reference)

## Cleanup

Old snapshots can be archived or removed if they are no longer needed. Keep at least the latest snapshot for new installations.
