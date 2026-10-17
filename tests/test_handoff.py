"""When does a buyer question go to the seller? Phrases below are the real answers from
the first live test (Oct 17), where answered questions were wrongly logged."""
import pytest

from backend.app.handoff import is_price_question, looks_unsure, question_key


@pytest.mark.parametrize(
    "answer",
    [
        "I don't know the size yet. Please ask the seller.",
        "I don’t know yet, I'll pass that to the seller.",  # curly apostrophe
        "The catalog does not specify the material.",
        "The exact material has not been confirmed.",
        "The seller hasn't mentioned the size.",
        "There is no information about delivery.",
        "I'm not sure, let me ask the seller.",
        "The size is unknown.",
    ],
)
def test_handoffs_are_detected(answer):
    assert looks_unsure(answer) is True


@pytest.mark.parametrize(
    "answer",
    [
        "The price is 100.",
        "The price of Handcrafted Silver Bracelet Trio is 100.",
        "They come in three colours: gold, silver and white.",
        "The seller says it is sterling silver.",
        "It's a set of three bracelets.",
        "Yes, it ships in 2 days.",
    ],
)
def test_real_answers_are_not_handoffs(answer):
    assert looks_unsure(answer) is False


@pytest.mark.parametrize("question", ["What's the price?", "how much does it cost", "How much is it?", "price?"])
def test_price_questions(question):
    assert is_price_question(question) is True


@pytest.mark.parametrize("question", ["What size is it?", "How much stock do you have?", "Is it nickel free?"])
def test_non_price_questions(question):
    assert is_price_question(question) is False


def test_same_question_worded_differently_has_the_same_key():
    assert question_key("What is it made of?", "p1") == question_key("what's it made of", "p1")


def test_same_question_about_a_different_product_has_a_different_key():
    assert question_key("What size?", "p1") != question_key("What size?", "p2")


# ---------- second round: found by probing the first fix with plausible replies ----------

@pytest.mark.parametrize(
    "answer",
    [
        # Pointing at the seller AFTER answering is not a hand-off. A 1B model adds this a lot.
        "You can contact the seller to order it.",
        "The seller says it ships within 2 days. Message the seller to place an order.",
        "It comes in gold, silver and white. Contact the seller to choose a colour.",
        "The seller can send more photos if you ask.",
        # These DO contain a "pass it on / ask the seller" phrase, but only after the answer.
        "Yes, it ships in 2 days. Ask the seller if you want a custom size.",
        "The bracelet is 6 cm wide. I can pass your photo request on to the seller.",
        "It comes in three colours. Check with the seller for restocks.",
        "Yes, it is nickel free, as confirmed by the seller.",
        "It's sterling silver, according to the seller.",
        "The bracelet is 6 cm wide.",
        "I can tell you it is a set of three.",
    ],
)
def test_pointing_at_the_seller_after_answering_is_not_a_handoff(answer):
    assert looks_unsure(answer) is False


@pytest.mark.parametrize(
    "answer",
    [
        "Sorry, I couldn't find that in the details.",
        "I'm afraid I can't help with that one.",
        "It might be silver, but I can't be certain.",
        "I think it is brass.",  # a guess is not an answer
        "Hmm, the catalog is silent on delivery.",
        "Please check with the seller about the size.",
        "I'll pass your request on to the seller.",
        "Let me forward that to the seller.",
    ],
)
def test_more_ways_of_not_knowing_are_detected(answer):
    assert looks_unsure(answer) is True


@pytest.mark.parametrize(
    "question",
    [
        "Is the price negotiable?",
        "What is the best price you can do?",
        "Does the price include delivery?",
        "How much for two?",
        "How much for 3 pieces?",
        "Is it worth the price?",
    ],
)
def test_questions_that_only_mention_the_price_are_not_answered_with_the_price(question):
    assert is_price_question(question) is False
