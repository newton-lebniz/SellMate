# Submission checklist: Week 2 (Side Hustle)

Deadline per the challenge page: **October 18**. The page doesn't say what time or time zone,
so don't plan to publish at the last minute. Aim to have the post live **by the morning of the 18th**
and use the rest of the day as buffer.

## Tonight (Oct 17)

- [ ] **Run the new version on your laptop** and take the three screenshots below.
  - Unzip the new files over your project folder, then start it the same way as before.
  - The first listing may take about a minute. That's normal.
- [ ] **Delete the old catalog** so the demo starts clean (the Day 2 data has the old, unguarded listing):
  `rm data/catalog.json data/questions.json` (leave `data/uploads/`; delete the old photo if you like).
- [ ] **Re-run your bracelet photo** with the same keywords. Check three things:
  - the title now says `Silver-coloured`
  - a red box lists anything removed, a yellow box says what to check
  - the "Ready to post" tabs show WhatsApp, Instagram and Reddit text
- [ ] **Type the real details** ("sterling silver" only if it's true!), press **Rewrite**, and note how many seconds it took.
- [ ] **Run the buyer questions**: price (should be instant), material, size. Check the inbox shows only what was unanswered.
- [ ] **Message one real seller.** See "First user" below. Do this tonight even if you can't test until tomorrow.

## Screenshots to take (these go in the post)

1. **Shop page** with a short chat: price answered, size passed to the seller.
2. **Seller desk** showing the red "Left out because nobody confirmed them" box and the yellow "Check before you post" box.
3. **The inbox** with a question and its "Asked N times" label.

Optional fourth: the `Ready to post` panel on the WhatsApp tab.

## Demo (60-90 seconds, screen recording)

1. Drop in the bracelet photo, type keywords, press **Write my listing**. (Cut the wait: say "about 40 seconds on my CPU laptop" over a jump cut.)
2. Point at the title: "it says silver-coloured, not silver, because I never told it the material."
3. Point at the red box: "it removed 'hand-tied' because I never said that."
4. Type the real details, press **Rewrite**.
5. Click through WhatsApp / Instagram / Reddit and copy one.
6. Open the shop page. Ask the price (instant), then the size ("it doesn't know, so it tells the buyer and tells me").
7. Show the inbox.

## First user (bonus points)

Anyone who sells things in DMs: a friend, a relative, a classmate with a side business, a seller you find on Instagram or Reddit.

- Run SellMate on your laptop and screen-share, or sit next to them. Don't ask them to install anything.
- Let them type their own item and keywords. Don't help.
- Ask: *Would you use this? What would you pay? What's missing? What annoyed you?*
- Write down their exact words and what they asked for next. Ask permission before you quote or name them.
- If nobody can try it in time, say so in one honest line. Don't invent a user.

## Before you press Publish

- [ ] Title and first paragraph are in your own voice (see the note at the top of `DEV_POST_DRAFT.md`)
- [ ] Every `[TODO]` is replaced or deleted
- [ ] The numbers match what you measured (22 s + 18 s, 168 tests; update if you re-measured)
- [ ] The "why open models mattered" section is there (the challenge asks for it explicitly)
- [ ] GitHub repo is **public**, `README.md` renders, `LICENSE` is present
- [ ] `data/catalog.json` and `data/questions.json` are **not** committed (they're in `.gitignore`; check `git status`)
- [ ] Screenshots don't show anything private (real names, phone numbers, addresses)
- [ ] The post uses DEV's submission template, which adds `#devchallenge` and `#hf26challenge`
- [ ] Optional: tag the Gemma category by mentioning Gemma 3 running locally

## After publishing

- [ ] Open the post logged out and check images and code blocks render
- [ ] Re-read the first paragraph once. It's what judges read first.
