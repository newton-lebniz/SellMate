# Architecture

```
┌──────────────┐  multipart   ┌───────────────────────────────┐
│   Browser    │─────────────▶│ FastAPI  (backend/app/main.py)│
│ (HTML/CSS/JS)│◀─────────────│  validate → resize → generate │
└──────────────┘     JSON     └───────┬──────────────┬────────┘
                                      │              │
                              ┌───────▼──────┐  ┌────▼─────────┐
                              │ llm.py       │  │ storage.py   │
                              │ Ollama /api/ │  │ catalog.json │
                              │ chat (Gemma) │  │ + uploads/   │
                              └──────────────┘  └──────────────┘
```

## Modules

| File | Responsibility |
| --- | --- |
| `config.py` | Environment-driven settings |
| `models.py` | `Listing` and `Product` schemas (pydantic) |
| `prompts.py` | System prompt and listing prompt (the honesty rules live here) |
| `llm.py` | Image preparation, Ollama call, tolerant JSON parsing |
| `storage.py` | Thread-safe JSON catalog with atomic writes |
| `main.py` | HTTP routes and upload validation |

## Design decisions

- **JSON file instead of a database.** One seller, one laptop, tens of items. Zero setup, easy to back up by copying a folder.
- **Atomic writes** (write temp file, then replace) so a crash never corrupts the catalog.
- **Downscale to 640px.** Cuts CPU inference time a lot with little quality loss for product photos, and strips EXIF/GPS as a side effect.
- **Tolerant JSON parsing.** Small models sometimes wrap JSON in prose or code fences, so the parser extracts the first object and validates it.
- **`missing_info` instead of guessing.** If material or size isn't visible or given, the model asks the seller instead of inventing it.
