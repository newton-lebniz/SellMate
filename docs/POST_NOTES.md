# DEV post notes

The full draft is in `DEV_POST_DRAFT.md`. This file is the fact sheet behind it: what we measured, what broke,
and what is still missing. The checklist for tonight and tomorrow is `SUBMISSION_CHECKLIST.md`.

Required tags: `#devchallenge` `#hf26challenge`. Theme: Side Hustle.

## Measured facts (your laptop, Oct 17 live test)

- Setup: 16 GB RAM, CPU only, Ollama on Windows, app in WSL, `moondream` + `gemma3:1b`
- One photo: Moondream **22.1 s**, Gemma 3 1B **18.2 s**, total about **40 s**
- Test suite: 23 tests on Day 1, 68 on Day 2, **168** after the Day 3 fixes
- `python scripts/mutation_check.py` reintroduces nine known bugs one at a time; all nine are caught
- [ ] Rewrite time (reuses the photo notes, so only the writing stage runs): ____ s
- [ ] Chat reply time: ____ s (price answers are instant, since they skip the model)

## What broke (all three are in the post)

1. **Passing tests, failing product.** Day 1: 23 stubbed tests passed; the real model returned a 400 because `gemma3:1b` can't read images, and the status light still said "ready".
2. **The model graded its own homework.** Day 2 asked Gemma to return `answered_from_catalog: true/false`. Live, it flagged correctly answered questions (price, material), so the seller's inbox filled with noise. Fixed by moving price out of the model and deciding hand-offs from the answer text.
3. **A colour became a metal.** Moondream said the bracelets were gold, silver and white (correct, as colours). Gemma wrote "Silver Bracelet" plus a "hand-tied" claim, while the seller's notes said the material was unconfirmed. Fixed with a deterministic claim guard.

The data behind #3 is kept as a fixture: `tests/fixtures/day2_bracelet.json`.

## Honest points to keep in the post

- The claim guard is a word list. It doesn't understand; it catches known words.
- "Silver" in the real listing was only a *colour* the model over-read. A bigger model wouldn't know the real material either. The fix was process, not model size.
- Where closed models would have been better: speed and caption detail.
- The inbox decision reads the wording of the answer, so an oddly phrased "I don't know" could slip through.
- The first version of the inbox fix over-corrected ("contact the seller to order" counted as a hand-off). Probing it with realistic replies found that; it's a good example of testing your own fix.

## Still needed from you

- [ ] First user: who, what they asked, whether they'd pay, what they asked for next
- [ ] Your pricing idea
- [ ] Three screenshots (see the checklist)
- [ ] Public GitHub link in the post

## Partner categories

- **Best Use of Gemma**: primary target (Gemma 3 1B running locally on CPU)
- Others are optional and only worth mentioning if actually used

## Day log

- **Day 1 (Oct 15):** scaffold, backend pipeline, simple UI, tests (23 passing, model stubbed).
- **Day 2 (Oct 16):** real-laptop test found the vision bug; two-stage fix; seller details, buyer chat, seller inbox.
- **Day 3 (Oct 17):** live test found two more bugs (false inbox entries, colour-as-metal); fixed with regression tests; added claim guard, rewrite-with-details, and ready-to-post copy. A second pass tightened the inbox detector and added an EXIF/GPS test and the mutation check.
