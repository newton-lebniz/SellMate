# SellMate

**A listing writer and buyer-chat assistant for solo sellers who run their shop out of WhatsApp.**
Upload a few photos and a few keywords. A local open-weight model (Gemma, via Ollama) writes the listing. Nothing leaves your laptop.

Built for the [DEV Hacktoberfest Open-Source AI Challenge, Week 2: Side Hustle](https://dev.to) (`#devchallenge` `#hf26challenge`).

---

## The problem

Thousands of tiny businesses (jewelry makers, thrift sellers, bakers, handmade crafts) sell through WhatsApp and Instagram DMs. Every sale starts the same way: a buyer messages, the seller sends photos, and then comes a long back-and-forth.

- "Is it real silver?"
- "What size is it?"
- "Do you have it in gold?"
- "Price?"

The seller answers the same questions all day, and writing a good description for each new item takes longer than making the item.

## Who would pay for this

A solo seller listing 10-30 items a month. SellMate turns "3 photos + a few words" into a polished, honest listing in a minute, and (coming in the next days) answers buyers' questions from the seller's own catalog.

## Why open models matter here

| Concern | Closed API | SellMate (open-weight, local) |
| --- | --- | --- |
| Cost per listing | Pay per token, forever | Zero marginal cost |
| Customer and product photos | Uploaded to someone else's server | Stay on the seller's machine |
| Photo metadata (EXIF, GPS) | Often forwarded as-is | Stripped before the model ever sees the image |
| Internet required | Yes | No (after the one-time model download) |
| Swap or fine-tune the model | Not possible | Change one env var: `OLLAMA_MODEL` |

A solo seller earning small margins can't afford a per-message API bill, and shouldn't have to hand a stranger's server their supplier photos and customer chats.

## How it works (Day 1)

```
photos + keywords ──▶ FastAPI ──▶ resize + strip EXIF ──▶ Gemma (Ollama, CPU) ──▶ JSON listing ──▶ catalog.json
```

1. Photos are resized to 640px and re-encoded as JPEG. This keeps CPU inference fast and drops EXIF/GPS metadata.
2. Gemma gets the photos, the seller's keywords, and strict rules: **only state what's visible or provided, and ask about anything a buyer would care about but can't be seen** (the `missing_info` field).
3. The reply is validated into a typed `Listing` and saved to a local JSON catalog.

## Quick start

Requires Python 3.10+ and [Ollama](https://ollama.com).

```bash
# 1. Get the model (vision-capable Gemma, runs on CPU)
ollama pull gemma3:4b

# 2. Install
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Run
uvicorn backend.app.main:app --reload
```

Open <http://127.0.0.1:8000>.

**CPU note:** on a CPU-only laptop the first listing can take 1-3 minutes while the model loads; later ones are faster. Use fewer or smaller photos if it feels slow. To try a different model:

```bash
OLLAMA_MODEL=gemma3:4b-it-qat uvicorn backend.app.main:app
```

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` | Where Ollama is running |
| `OLLAMA_MODEL` | `gemma3:4b` | Vision-capable model to use |
| `OLLAMA_TIMEOUT` | `300` | Seconds to wait for a response |
| `SELLMATE_DATA_DIR` | `./data` | Where the catalog and photos are stored |

## Tests

```bash
pytest
```

The tests run without Ollama (the model call is stubbed).

## Roadmap

- [x] **Day 1:** photo + keywords to listing, local catalog, simple web UI
- [ ] **Day 2:** buyer chat page that answers only from the seller's catalog
- [ ] **Day 3:** platform-ready copy for WhatsApp / Instagram / Reddit, demo, DEV post

## License

MIT
