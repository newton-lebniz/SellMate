# SellMate

**A listing writer and buyer-chat assistant for solo sellers who run their shop out of WhatsApp.**
Upload a few photos and a few keywords. Small open-weight models running on your own laptop write the listing, then answer buyers' questions using only the facts you gave them. Nothing leaves your machine.

Built for the DEV Hacktoberfest Open-Source AI Challenge, Week 2: **Side Hustle** (`#devchallenge` `#hf26challenge`).

---

## The problem

Thousands of tiny businesses (jewelry makers, thrift sellers, bakers, handmade crafts) sell through WhatsApp and Instagram DMs. Every sale starts the same way: a buyer messages, the seller sends photos, and then comes a long back-and-forth.

- "Is it real silver?"
- "What size is it?"
- "Do you have it in gold?"

The seller answers the same questions all day, and writing a good description for each new item takes longer than making the item.

## What SellMate does

1. **Seller desk.** Drop 1-3 photos and a few keywords. SellMate writes a title, description, highlights and tags.
2. **It asks instead of guessing.** Anything buyers care about that the photo can't show (material, size, delivery) comes back as a question for the seller. The seller types the answers once.
3. **Shop page.** Buyers ask questions in a chat. The assistant answers **only** from the listing and the seller's own details.
4. **Seller inbox.** If the assistant doesn't know, it says so, tells the buyer the question was passed on, and the seller sees it on the desk.

## Why open models matter here

| Concern | Closed API | SellMate (open-weight, local) |
| --- | --- | --- |
| Cost per listing or chat reply | Pay per token, forever | Zero marginal cost |
| Product photos and buyer chats | Uploaded to someone else's server | Stay on the seller's machine |
| Photo metadata (EXIF, GPS) | Often forwarded as-is | Stripped before any model sees the image |
| Internet required | Yes | No (after the one-time model download) |
| Swap or fine-tune the model | Not possible | One environment variable per model |
| Runs on a CPU-only laptop | n/a | Yes: a 1B text model plus a tiny vision model |

## How it works

```
                 seller desk                                   shop page
photos + keywords                                        buyer question
        │                                                       │
        ▼                                                       ▼
resize + strip EXIF                                  pick the 1-3 matching products
        │                                                       │
        ▼                                                       ▼
 Moondream (looks at each photo)                      Gemma 1B answers from those
        │  "a small round silver ring..."               facts only (JSON: answer +
        ▼                                               answered_from_catalog)
 Gemma 1B writes the listing                                    │
 (photo notes + seller's words)                       grounded?  yes → show answer
        │                                                        no  → show answer,
        ▼                                                              log the question
   catalog.json                                                        for the seller
```

Why two models? A 1B text model writes well but cannot see images, and a vision-capable 4B model is heavy on a CPU-only laptop. A tiny vision model describes the photo, and the text model does the writing. If you have the hardware, set `VISION_MODEL=` (empty) and use a vision-capable model such as `gemma3:4b` as the only model.

## Quick start

Requires Python 3.10+ and [Ollama](https://ollama.com).

```bash
# 1. Get the models (both are small enough for a CPU laptop)
ollama pull moondream
ollama pull gemma3:1b

# 2. Install
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Run
uvicorn backend.app.main:app --reload
```

- Seller desk: <http://127.0.0.1:8000>
- Shop page (what buyers see): <http://127.0.0.1:8000/shop.html>

The pill at the top of the seller desk tells you which models are ready. On a CPU, the first listing can take a few minutes while models load; later ones are faster.

**Ollama on Windows, SellMate in WSL?** Point SellMate at the Windows host, and make sure Ollama listens beyond localhost (`OLLAMA_HOST=0.0.0.0` on the Windows side):

```bash
export OLLAMA_URL="http://<windows-host-ip>:11434"   # find it with: ip route show | grep default
```

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_URL` | `http://localhost:11434` | Where Ollama is running |
| `OLLAMA_MODEL` | `gemma3:1b` | Text model: writes listings, answers buyers |
| `VISION_MODEL` | `moondream` | Looks at photos. Empty = send photos to `OLLAMA_MODEL` (needs a vision model) |
| `OLLAMA_TIMEOUT` | `300` | Seconds to wait for each model call |
| `SELLMATE_DATA_DIR` | `./data` | Where the catalog, questions and photos are stored |

## Tests

```bash
pytest
```

The tests use a fake Ollama, so they run anywhere. They include the two-stage pipeline: the text model must never receive images, and must receive what the vision model saw.

## Honest limitations

- **Small models are vague.** Moondream gives short, generic captions, and Gemma 1B sometimes writes plain prose. That's why the seller's own details outrank the photo notes everywhere.
- **"Grounded" is self-reported.** The assistant says whether its answer came from the catalog facts. A 1B model can be wrong about that, so treat the seller inbox as a safety net, not a guarantee.
- **No login yet.** This is a single-seller local tool. Don't expose it to the internet as it is.
- **CPU is slow.** Expect tens of seconds per reply, and minutes for a first listing.

## Roadmap

- [x] **Day 1:** photo + keywords to listing, local catalog, simple web UI
- [x] **Day 2:** two-stage vision fix, seller details, buyer chat grounded in the catalog, seller inbox
- [ ] **Day 3:** platform-ready copy for WhatsApp / Instagram / Reddit, demo, DEV post

## License

MIT
