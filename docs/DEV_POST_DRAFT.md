<!--
HOW TO USE THIS DRAFT (delete this block before posting)

1. Everything marked [TODO] is something only you know. Don't leave a [TODO] in the post,
   and don't make up an answer: if you have no first user, delete that section and say so
   in one honest line instead.
2. Every number below is from your own runs (Oct 17 live test) or from the test suite.
   If you re-measure, update them.
3. Rewrite the first paragraph and the closing in your own voice. The structure and the
   facts are solid; the voice has to be yours.
4. DEV's submission template adds the required tags (#devchallenge, #hf26challenge).
5. Add screenshots where marked [IMAGE]. The three that matter most are listed in
   docs/SUBMISSION_CHECKLIST.md.
6. This is written as "I", about code you built with an AI coding assistant. Say so plainly
   somewhere (one line is enough). DEV's template even invites you to share the agent session.
   Decide how you want to credit it, but don't leave it out.
-->

# I built a shop assistant for WhatsApp sellers on a CPU-only laptop. The hard part was teaching it to say "I don't know."

If you've ever bought handmade jewellery over WhatsApp or Instagram DMs, you know the script. You send "price?", the seller sends photos, you ask what it's made of, you ask the size, you ask if it comes in another colour. Multiply that by every buyer, every item, every day, and you have a solo seller who spends more time typing the same answers than making things.

SellMate is my attempt to take that job off their plate. You drop in a photo and a few keywords. It writes the listing, gives buyers a chat page where they can ask questions, and puts anything it can't answer in your inbox. It runs entirely on my laptop (16 GB RAM, no GPU) using two small open models through Ollama.

[IMAGE: the shop page with a short buyer chat]

## Who would pay for this

A solo seller with a catalogue they keep re-describing in DMs. [TODO: who you'd charge and roughly what, or what your first user said about price. If you don't have this yet, say what you'd test next.]

## How it works

A 1B-parameter text model writes well but can't see images. A vision model that can see is heavy on a laptop without a GPU. So I used two small models, each doing one job:

1. **Moondream** looks at the photo and describes how it *looks*.
2. **Gemma 3 1B** writes the listing from that description plus what the seller typed.

On my machine, one photo took about 22 seconds to look at and 18 seconds to write. That's slow next to a hosted API, and I'll come back to that.

Buyers use a separate shop page. Their questions go to Gemma again, but it only sees the one to three products that match the question, and it's told to answer only from the seller's facts. If it doesn't know, it says so, tells the buyer the question was passed on, and the seller sees it in an inbox.

[IMAGE: the seller desk with a listing, the "check before you post" box, and the inbox]

## Why open models mattered

- **It costs nothing per message.** A seller with thin margins can't take a per-token bill on every "what's it made of?"
- **The photos and chats never leave the laptop.** Photos are also re-encoded before any model sees them, which strips location data from the EXIF.
- **I could change the architecture when something broke.** When I found my text model couldn't read images, the fix was to add a second model and change one environment variable. With a closed API I'd have been choosing between vendors, not designing a pipeline.

Where a closed model would very likely have been better: speed and caption detail. I didn't benchmark one, so that's an expectation, not a measurement. But, as you'll see, the failures I hit weren't the kind a bigger model fixes.

## Three things that broke

This is the part I learned the most from.

### 1. 23 tests passed and the real model still failed

On Day 1 my tests passed. Then I ran SellMate for real and got `Ollama returned an error (400)`. `gemma3:1b` is text-only and rejects image input. My tests stubbed the model, so they could never have caught it. Worse, the status light said `gemma3:1b ready`, because the health check only knew the model was *downloaded*, not that it could *see*.

The fix was the two-model pipeline, a health check that reports each model separately, and a test that asserts the text model never receives an image.

### 2. I asked the model to grade its own homework

For the inbox, I had Gemma return `answered_from_catalog: true/false` alongside every answer. On the first live test, a buyer asked "What's the price?" and Gemma answered correctly ("The price is 100"), and the question still landed in the seller's inbox, next to repeats of the same material question.

A 1B model can't be trusted to judge its own answer. The fix had two parts: plain price questions no longer go to the model at all (the answer comes from the price field, instantly and always correct), and the "needs the seller" decision now comes from plain code that reads what the answer says. Repeated questions are counted instead of repeated.

My first version of that fix was wrong in the other direction. When I tried it on realistic replies, "You can contact the seller to order it" was treated as "I don't know", which is the original bug again, and "Sorry, I couldn't find that in the details" slipped through, which means a buyer's question never reaches the seller. Both failures cost something: noise teaches the seller to stop checking the inbox, and a missed question is a lost sale. Pointing at the seller now only counts when it's how the reply *opens*, and "Is the price negotiable?" no longer gets answered with just the price.

### 3. A colour became a metal

This is the one that matters for a shop. My bracelet photo showed three bracelets: gold, silver and white. Moondream said so, correctly, as colours. Gemma wrote:

> **Handcrafted Silver Bracelet Trio** ... tags: `silver bracelet`

and a description claiming a "hand-tied design". Meanwhile the seller's own notes said the material was unconfirmed. A buyer reads "silver bracelet" as the metal. Telling the model "don't invent materials" in the prompt didn't stop it.

So I added a claim guard: plain code that runs on every generated listing and compares its claims against what the **seller** supplied (never the photo notes):

| | Before | After |
|---|---|---|
| Title | Handcrafted Silver Bracelet Trio | Handcrafted Silver-coloured Bracelet Trio |
| Tag | `silver bracelet` | `silver-coloured bracelet` |
| "hand-tied design" | in the description | removed, and the seller is asked |
| "Handmade" | kept | kept (the seller typed it) |

Once the seller confirms "sterling silver, hand-tied with cotton thread" and presses *Rewrite*, the guard stops removing those claims. The guard is a word list, not understanding, so it won't catch everything, and I say so in the README. But it's the difference between a tool that *tries* to be honest and one that's checked.

I wrote regression tests for all three problems, using the real bracelet listing as a fixture. The test suite is now 168 tests. A regression test that can't fail isn't one, so `python scripts/mutation_check.py` puts nine of the bugs back, one at a time, in a scratch copy and checks that the tests fail each time. They do. (My first run missed one, which is how I found a test that wasn't testing what it claimed.)

## What it's like to use

1. Drop in a photo, type "handmade bracelets", price, category.
2. Read the listing. A red box shows what was removed; a yellow box shows what to check.
3. Type what's true ("Sterling silver, ships in 2 days"), press **Rewrite**.
4. Copy the WhatsApp, Instagram or Reddit version.
5. Buyers ask questions on the shop page. Price is instant. Anything it doesn't know lands in your inbox.

## First user

[TODO: Who tried it, what they asked, what confused them, whether they said they'd pay, and what they asked for next. Keep it specific and honest, even if the honest answer is "it was too slow." If you haven't had a user yet, replace this section with one line saying so and what you'd ask them.]

## What I'd do next

- A faster vision step. 22 seconds per photo is the biggest wait.
- Let sellers teach it their own words, so it learns that "kada" is a bangle.
- A login, so it can leave my laptop.

## Try it

[TODO: GitHub link: github.com/newton-lebniz/SellMate]

It needs Python and Ollama:

```bash
ollama pull moondream
ollama pull gemma3:1b
pip install -r requirements.txt
uvicorn backend.app.main:app
```

*Built with Gemma 3 (1B) and Moondream, running locally via Ollama, for the Hacktoberfest Open-Source AI Challenge, Week 2.*
