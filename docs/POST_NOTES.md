# DEV post notes (writing quality is weighted most, so collect material as we build)

Required tags: `#devchallenge` `#hf26challenge`. Theme: Side Hustle.

## Post outline

1. **The seller** - one real person's problem (the WhatsApp back-and-forth). Open with a concrete scene, not "In today's world".
2. **What I built** - SellMate in two sentences + a demo GIF/screenshots (seller desk and shop page).
3. **Who would pay and why** - solo sellers, per-month pricing idea.
4. **Why open models mattered** (the section judges explicitly ask for)
   - Cost: zero marginal cost per listing and per chat reply
   - Privacy: photos and chats never leave the laptop
   - Control: two models, each swappable with one env var; I changed the architecture when one model couldn't see
   - Be honest about where it was *worse* than a closed model (speed on CPU, vague captions, small-model slips)
5. **How I built it** - the two-stage pipeline, grounded chat, the seller inbox.
6. **The bug that tests didn't catch** (see below). This is the most "real" part of the story.
7. **First user** (bonus points) - who, what they said, would they pay, what they asked for next.
8. **What's next**.

## The bug story (use this)

- Day 1: 23 tests passed. I ran it for real on a CPU-only laptop with `gemma3:1b`.
- Real result: `Ollama returned an error (400)`. The model said it "does not support multimodal requests". My tests stubbed the model, so they could never have caught it.
- Also: the green "ready" pill said `gemma3:1b ready` even though photo requests failed. The health check only knew the model was *downloaded*, not that it could *see*.
- Fix: a tiny vision model (Moondream) describes the photo, and Gemma 1B writes the listing from that description plus the seller's words. The health check now reports both models separately, and a test asserts the text model never receives images.
- Lesson worth one paragraph: stubbed tests prove your logic, not your integration.

## Facts to capture as we go

- [ ] Seconds per listing on my CPU, vision stage and writing stage (the UI shows both): ____ / ____
- [ ] Seconds per chat reply: ____
- [ ] Models: moondream + gemma3:1b, RAM: 16 GB, CPU only
- [ ] One example where Moondream's caption was wrong or vague, and how the seller's keywords fixed it
- [ ] One example where the assistant correctly said "I don't know" and the question reached the seller inbox
- [ ] One example where it answered when it shouldn't have (be honest, it makes the post credible)
- [ ] Screenshots: `missing_info` box, shop chat, seller inbox
- [ ] First user's name/handle (ask permission), quote, price they'd pay, what they asked for next

## Partner categories worth mentioning

- **Best Use of Gemma** - primary target (local Gemma on CPU)
- **Best Use of GitHub Copilot / Entire** - optional, only if actually used
- **.tech domain** - optional, only if we deploy

## Day log

- **Day 1 (Oct 15):** scaffold, backend pipeline, simple UI, tests (23 passing, model stubbed).
- **Day 2 (Oct 16):** real-laptop test found the vision bug; two-stage fix; seller details, grounded buyer chat, seller inbox; 68+ tests including a fake-Ollama browser run.
