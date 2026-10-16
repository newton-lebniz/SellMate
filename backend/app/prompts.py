"""Prompts. The honesty rules here are the heart of the product: a seller's
reputation suffers if the assistant invents a material or a size."""

SYSTEM_PROMPT = (
    "You are SellMate, an assistant that writes honest, appealing product listings "
    "for small solo sellers who sell through WhatsApp, Instagram and Reddit.\n"
    "Rules:\n"
    "1. Only state facts that are visible in the photos or given by the seller. "
    "Never invent materials, sizes, brands, weights or certifications.\n"
    "2. If a detail buyers usually ask about is unknown (material, size, colour options, "
    "condition, delivery), do NOT guess. Add a short question for the seller to "
    "'missing_info' instead.\n"
    "3. Write in warm, plain, specific language. Avoid hype words like 'amazing', "
    "'stunning' or 'must-have'.\n"
    "4. Reply with a single JSON object and nothing else."
)

LISTING_SCHEMA = """{
  "title": "max 70 characters",
  "description": "60 to 110 words, one or two short paragraphs",
  "highlights": ["3 to 5 short bullet points"],
  "tags": ["5 to 8 lowercase search keywords, no # symbol"],
  "missing_info": ["questions for the seller about details not visible or not provided"]
}"""


def build_listing_prompt(keywords: str, price: str | None, category: str | None) -> str:
    lines = [
        "Write a listing for the product in the attached photo(s).",
        f"Seller's keywords: {keywords}",
    ]
    if category:
        lines.append(f"Category: {category}")
    if price:
        lines.append(f"Price: {price}")
    lines.append("")
    lines.append("Return JSON in exactly this shape:")
    lines.append(LISTING_SCHEMA)
    return "\n".join(lines)
