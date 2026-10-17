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
| `claims.py` | Claim guard: removes or softens listing claims the seller never confirmed |
| `handoff.py` | Decides when a buyer question goes to the seller (price detection, "I don't know" detection, duplicate keys) |
| `copywriter.py` | WhatsApp / Instagram / Reddit text from a saved listing (templates, no model) |
| `storage.py` | Thread-safe JSON catalog and capped question log, with atomic writes |
| `main.py` | HTTP routes and input validation |

## Photo to listing (two stages)

1. Photos are resized to 640px and re-encoded as JPEG (faster on CPU, and EXIF/GPS is dropped).
2. **Stage 1:** Moondream describes each photo, one call per photo (small vision models handle one image at a time).
3. **Stage 2:** Gemma 1B receives the photo notes plus the seller's keywords, price and category, and returns a JSON listing, including `missing_info` questions for anything it can't know.
4. In single-model mode (`VISION_MODEL` empty), stage 1 is skipped and the photos go straight to a vision-capable text model.

## Buyer chat

1. The buyer's question is matched against the catalog by keyword overlap (title, tags, keywords and category count triple). Only the top 3 products reach the model. If the buyer picked an item, only that one is sent.
2. **Price questions never reach the model.** If one item is in play, the answer comes straight from the price field. No price set means a hand-off.
3. Otherwise the prompt contains plain-text catalog facts. The seller's own details are marked as the most reliable source; photo notes are marked as possibly wrong. If the seller hasn't answered a `missing_info` question yet, the facts say "not known yet".
4. Gemma replies in **plain text**, and is told to begin with "I don't know yet" when the facts don't cover the question.
5. `handoff.looks_unsure()` reads the answer. If it says it doesn't know or points to the seller, the question goes to `questions.json`; the same question about the same product bumps a counter instead of adding a row.

## Listing guard

After every generation (first write and every rewrite), `claims.guard()` compares the listing with what the **seller** supplied (keywords, category, details; never photo notes):

- **Hard claims** (materials, hand techniques, "real" vs "plated" metal, quality words like hypoallergenic): removed from the title, tags, highlights and description if unsupported. Each claim needs its own support, so "nickel free" doesn't vouch for "hypoallergenic" and "hand-woven" doesn't vouch for "hand-tied".
- **Soft claims** ("silver", "gold" in the title or tags, where a buyer reads a metal): kept, rewritten as "silver-coloured", and the seller is asked.
- The seller is asked about each, via `missing_info`. Confirming a fact in "Your details" and pressing Rewrite puts the claim back.

## Design decisions

- **JSON files instead of a database.** One seller, one laptop, tens of items. Zero setup, and a backup is copying a folder.
- **Atomic writes** (temp file, then replace) so a crash never corrupts the catalog.
- **Two small models instead of one big one.** A 1B text model plus a tiny vision model fits a 16 GB CPU-only laptop. The cost is two sequential calls, which `vision_seconds` and `writing_seconds` record per listing.
- **Keyword retrieval, not embeddings.** A seller's catalog is tens of items, and an embedding model would be one more download on a CPU-only machine.
- **Tolerant JSON parsing.** Small models wrap JSON in prose or code fences, so the parser extracts the first object and validates it.
- **Don't ask a small model to grade itself.** Day 2 had Gemma report `answered_from_catalog: true/false`. On the first real run it flagged correctly answered questions, so the check moved to plain code that reads the answer, and price moved out of the model entirely.
- **Deterministic guards after the model.** A prompt that says "don't invent materials" didn't stop a 1B model turning a silver *colour* into a silver *metal*. A word-list check on the output does, and it's testable.
- **Platform copy is templates.** The listing was already written and checked once; three more model calls would cost minutes of CPU and add three chances to invent something.
- **Model output is untrusted.** The frontend never uses `innerHTML`, and buyer messages are told to be ignored if they try to change the assistant's rules.
- **Old catalogs keep loading.** New `Product` fields have defaults, with a test for Day 1 data.
