# DEV post notes (writing quality is weighted most, so collect material as we build)

Required tags: `#devchallenge` `#hf26challenge`. Theme: Side Hustle.

## Post outline

1. **The seller** - one real person's problem (the WhatsApp back-and-forth). Open with a concrete scene, not "In today's world".
2. **What I built** - SellMate in two sentences + a demo GIF/screenshot.
3. **Who would pay and why** - solo sellers, per-month pricing idea.
4. **Why open models mattered** (the section judges explicitly ask for)
   - Cost: zero marginal cost per listing
   - Privacy: photos and chats never leave the laptop
   - Control: swapped models with one env var, tuned the prompt rules
   - Be honest about where it was *worse* than a closed model (speed on CPU, quality on small details)
5. **How I built it** - architecture, the CPU constraints, what I'd change.
6. **First user** (bonus points) - who, what they said, would they pay, what they asked for next.
7. **What's next**.

## Facts to capture as we go

- [ ] Seconds per listing on my CPU (cold start vs warm): ____
- [ ] Model + size used: gemma3:4b
- [ ] One example where Gemma got something wrong or invented a detail, and how the prompt rules fixed it
- [ ] Screenshot of the `missing_info` questions (this is the honesty feature)
- [ ] First user's name/handle (ask permission), quote, price they'd pay

## Partner categories worth mentioning

- **Best Use of Gemma** - primary target (local Gemma on CPU)
- **Best Use of GitHub Copilot / Entire** - optional, only if actually used
- **.tech domain** - optional, only if we deploy

## Day log

- **Day 1 (Oct 15):** scaffold, backend pipeline, simple UI, tests.
