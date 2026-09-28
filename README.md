# Pulpo Cookie

Pulpo Cookie is a local Windows desktop character simulation built around Pulpo Cookie. It launches the cached Qwen3.5-9B Q4_K_M model through llama.cpp, streams Pulpo Cookie's visible response into a native Qt window, and stores continuity locally in SQLite.

## Start

Double-click `PulpoAI.pyw`, or run:

```powershell
python launcher.py
```

The first startup places the model on the GPU. The normal chat never requires a browser or a separately started server. Pulpo Cookie is tuned for responsive, natural in-character replies; it uses the immediately relevant turns as live context, shows the first word immediately, and streams the rest smoothly into its bubble.

## Current milestone

- Native PySide6 desktop window with streaming chat and a first-meeting scene opener
- Automatic hidden `llama-server` lifecycle management
- Saved-scene browser: start new conversations, return to earlier transcripts, or delete a selected chat with confirmation
- Qwen3.5-9B Q4_K_M with GPU offload, flash attention, a focused 3072-token context, compact KV cache, and tuned CPU workers
- Reasoning disabled with current llama.cpp flags, plus a display/storage safety filter
- Evidence-classified Pulpo canon files and relevance-based prompt assembly
- Persistent conversations, memory, scene, relationship history, and per-character knowledge
- Continuous, reversible non-romantic relationship dimensions (the extra model-driven analysis is off by default for faster chat and can be re-enabled in `data/settings.json`)
- Developer diagnostics with prompt components and relationship explanations
- Transactional SQLite writes, on-close backup, manual backup, and JSON export

Conversations are saved immediately. Starting a new scene never deletes the previous one. You can delete a selected chat from the sidebar; this removes that chat's messages, while shared long-term memories and relationship history remain available across saved scenes.

## Data boundaries

Canon lives in `characters/pulpo` and is never changed by roleplay. Simulation history lives in `data/pulpo.db`. A separate user-authored Pulpo analysis was mentioned in the original specification but was not included with the supplied attachment, so uncertain areas remain explicitly marked `UNKNOWN`.

## Development

```powershell
python -m pip install -r requirements.txt
python -m pytest
```

Logs are written to `logs/pulpo.log` and `logs/llama-server.log`. Local backups and exports are placed under `data/backups` and `data/exports`.

## Canon source policy

Each entry uses one of: `DIRECT_CANON_FACT`, `CANON_SUPPORTED_INFERENCE`, `USER_REPORTED_INGAME`, `INTERPRETATION`, or `UNKNOWN`. Source metadata and URLs live in `characters/pulpo/sources/sources.json`. Wiki material is labeled as documentation or transcription of game material rather than silently treated as an official first-party page.
