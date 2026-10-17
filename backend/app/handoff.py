"""Decide when a buyer question must go to the seller.

Day 2 trusted the model to report whether its own answer was grounded in the catalog
("answered_from_catalog": true/false). A 1B model is unreliable at that: on the first
live test, correctly answered questions ("What's the price?") were logged as unanswered.

So the decision no longer depends on a flag the model fills in:
  1. Plain price questions are answered straight from the price field, with no model call.
  2. For everything else, the model is told to start with "I don't know yet" when the
     facts don't cover the question, and we look at what the answer actually says.

Two ways to get this wrong, and both cost the seller something:
  - false alarm: an answered question lands in the inbox (noise, the seller stops looking)
  - missed gap: a question nobody could answer never reaches the seller (a lost sale)
Tests keep real examples of both (tests/test_handoff.py).
"""
import re

from .retrieval import tokenize

PRICE_QUESTION = re.compile(
    r"\b(price|prices|pricing|cost|costs|how much (is|are|for|does|do))\b", re.IGNORECASE
)

# "Is the price negotiable?", "Does the price include delivery?", "How much for two?" mention
# the price but ask something else. Answering them with just the price would be wrong, so
# they go to the model (which is told it can't negotiate) and, if it can't answer, to the seller.
NOT_A_PLAIN_PRICE_ASK = re.compile(
    r"\b(negotiab\w*|negotiat\w*|discount\w*|bargain\w*|best|final|last|lowest|cheaper|lower|"
    r"reduc\w*|includ\w*|worth|shipping|delivery|postage|gst|tax|emi|bulk|wholesale|"
    r"two|three|four|each|both|more than|extra|per)\b|\d",
    re.IGNORECASE,
)

# Phrases that mean "I couldn't answer this" anywhere in the reply. Checked on a normalised
# copy (contractions expanded), so "doesn't specify" and "does not specify" are the same.
UNSURE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bi do not (know|have)\b",
        r"\b(is|are|was|were|does|do|did|has|have|had) not (been )?"
        r"(specif\w*|mention\w*|say|said|stat\w*|list\w*|provid\w*|includ\w*|confirm\w*|"
        r"known|given|available|clear|set|decided|sure|certain)\b",
        r"\bnot (yet )?(been )?(sure|certain|known|available|specified|mentioned|stated|"
        r"confirmed|provided|listed|given|clear|decided)\b",
        r"\bno (information|info|details?)\b",
        r"\b(unknown|unsure|unclear|unconfirmed|unspecified)\b",
        r"\bcannot (say|tell|confirm|help|answer|find|be (sure|certain))\b",
        r"\bcould not find\b",
        r"\bsilent (on|about)\b",
        # A hedge is a guess, and the assistant must not guess.
        r"\b(i (think|guess|assume|suppose)|probably|possibly|perhaps)\b",
    )
]

# Pointing the buyer back to the seller only means "I couldn't answer" when it is how the reply
# OPENS. "It ships in 2 days. Contact the seller to order." answered the question.
HANDOFF_OPENING_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(ask|check with|checking with)\s+(the\s+)?seller\b",
        r"\bpass(ed|ing)?\s+(that|this|it|your\s+(question|query|request)|"
        r"the\s+(question|query|request))\b.*\bseller\b",
        r"\blet\s+(the\s+)?seller\s+know\b",
        r"\bforward(ed|ing)?\b.*\bseller\b",
        r"\bseller\b.*\b(get back|will confirm|will check|will let you know)\b",
    )
]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def is_price_question(text: str) -> bool:
    """True for a plain 'what does it cost?' that the price field can answer on its own."""
    text = text or ""
    return bool(PRICE_QUESTION.search(text)) and not NOT_A_PLAIN_PRICE_ASK.search(text)


def _normalise(text: str) -> str:
    text = (text or "").replace("’", "'").lower()
    text = re.sub(r"\bcan't\b", "cannot", text)
    text = re.sub(r"\bwon't\b", "will not", text)
    text = re.sub(r"n't\b", " not", text)
    return re.sub(r"\s+", " ", text)


def looks_unsure(answer: str) -> bool:
    """True if the answer says it doesn't know, or opens by handing the question to the seller."""
    text = _normalise(answer)
    if any(p.search(text) for p in UNSURE_PATTERNS):
        return True
    opening = _SENTENCE_END.split(text.strip(), maxsplit=1)[0]
    return any(p.search(opening) for p in HANDOFF_OPENING_PATTERNS)


def question_key(question: str, product_id: str | None) -> str:
    """Same question about the same product -> same key ('What is it made of?' and
    "what's it made of" both reduce to the words that matter)."""
    words = sorted(tokenize(question)) or [re.sub(r"\W+", " ", (question or "").lower()).strip()]
    return f"{product_id or '-'}:{' '.join(words)}"
