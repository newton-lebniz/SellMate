# Architecture

```
┌──────────────┐  multipart / JSON  ┌────────────────────────────────────┐
│   Browser    │───────────────────▶│ FastAPI  (backend/app/main.py)     │
│ seller desk  │◀───────────────────│  upload → resize → generate        │
│ shop page    │        JSON        │  chat   → retrieve → answer        │
└──────────────┘                    └───────┬──────────────┬─────────────┘
                                            │              │
                              ┌─────────────▼───┐   ┌──────▼─────────────┐
                              │ llm.py          │   │ storage.py         │
                              │ Ollama /api/chat│   │ catalog.json       │
                              │ moondream+gemma │   │ questions.json     │
                              └─────────────────┘   │ uploads/           │
                                                    └────────────────────┘
```

## Modules

| File | Responsibility |
| --- | --- |
| `config.py` | Environment-driven settings and limits |
| `models.py` | `Listing`, `Product`, chat request/response, `Question` schemas (pydantic) |
| `prompts.py` | Vision, listing and chat prompts (the honesty rules live here) |
| `llm.py` | Image prep, Ollama calls, two-stage generation, tolerant JSON parsing, health check |
| `retrieval.py` | Keyword retrieval: which products does the model see for this question? |
| `storage.py` | Thread-safe JSON catalog and capped question log, with atomic writes |
| `main.py` | HTTP routes and input validation |

## Photo to listing (two stages)

1. Photos are resized to 640px and re-encoded as JPEG (faster on CPU, and EXIF/GPS is dropped).
2. **Stage 1:** Moondream describes each photo, one call per photo (small vision models handle one image at a time).
3. **Stage 2:** Gemma 1B receives the photo notes plus the seller's keywords, price and category, and returns a JSON listing, including `missing_info` questions for anything it can't know.
4. In single-model mode (`VISION_MODEL` empty), stage 1 is skipped and the photos go straight to a vision-capable text model.

## Buyer chat

1. The buyer's question is matched against the catalog by keyword overlap (title, tags, keywords and category count triple). Only the top 3 products reach the model. If the buyer picked an item, only that one is sent.
2. The prompt contains plain-text catalog facts. The seller's own details are marked as the most reliable source; the vision model's notes are marked as possibly wrong. If the seller hasn't answered a `missing_info` question yet, the facts say "not known yet".
3. Gemma replies with JSON: `{"answer": "...", "answered_from_catalog": true|false}`.
4. If `answered_from_catalog` is not exactly `true` (missing, a string, or plain prose instead of JSON), the question is stored in `questions.json` for the seller.

## Design decisions

- **JSON files instead of a database.** One seller, one laptop, tens of items. Zero setup, and a backup is copying a folder.
- **Atomic writes** (temp file, then replace) so a crash never corrupts the catalog.
- **Two small models instead of one big one.** A 1B text model plus a tiny vision model fits a 16 GB CPU-only laptop. The cost is two sequential calls, which `vision_seconds` and `writing_seconds` record per listing.
- **Keyword retrieval, not embeddings.** A seller's catalog is tens of items, and an embedding model would be one more download on a CPU-only machine.
- **Tolerant JSON parsing.** Small models wrap JSON in prose or code fences, so the parser extracts the first object and validates it.
- **Fail toward the seller.** Any doubt about whether an answer was grounded means the question goes to the seller's inbox.
- **Model output is untrusted.** The frontend never uses `innerHTML`, and buyer messages are told to be ignored if they try to change the assistant's rules.
- **Old catalogs keep loading.** New `Product` fields have defaults, with a test for Day 1 data.
