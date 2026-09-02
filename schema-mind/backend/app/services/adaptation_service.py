"""
Adaptation service.
When the user struggles, this service regenerates patterns using different
approaches — simpler language, different format, more examples, etc.
"""
import json

from app.models.schemas import AdaptPatternsRequest, AdaptPatternsResponse
from app.services.groq_client import GroqClient
from app.services.pattern_service import completion_budget, parse_patterns

DEFAULT_NOTE = "Patterns adapted based on your progress."


SYSTEM_PROMPT = """You are SchemaMind Adapt. The user failed to remember certain concepts using the initial patterns.
Your job is to adapt and try a DIFFERENT approach.

Output valid JSON:
{
  "adapted_patterns": [
    {
      "type": "acronym" | "acrostic" | "analogy" | "number" | "story" | "custom",
      "label": "Short label",
      "content": "The adapted pattern",
      "variation": 1
    }
  ],
  "adaptation_note": "Brief explanation of what you changed and why"
}

RULES:
1. Generate EXACTLY FOUR distinct variations per pattern type you produce — no more, no less. Number them "variation": 1, 2, 3, 4 within each type.
2. The four variations of a type must take noticeably DIFFERENT approaches — different angles, imagery, or examples — never four rephrasings of the same idea.
3. If a pattern type failed, SWITCH to a different type for that content.
4. If the user got specific concepts wrong, focus on those concepts.
5. Use simpler language, more vivid imagery, more concrete examples.
6. Keep it concise — adapt, don't rewrite everything. Do not repeat the source text.
7. Output only the JSON object — no markdown, no commentary."""


async def adapt_patterns(req: AdaptPatternsRequest) -> AdaptPatternsResponse:
    client = GroqClient()

    prefs_str = ", ".join(
        (p.custom_description or "custom") if p.type == "custom" else p.type
        for p in req.preferences
    ) or "any"

    wrong_items = "\n".join(f"- {w}" for w in req.wrong_answers) if req.wrong_answers else "None yet"
    failed_types = ", ".join(req.failed_pattern_types) if req.failed_pattern_types else "None"

    user = f"""The user is studying this text:
---START---
{req.original_text.strip()}
---END---

Their preferred pattern types: {prefs_str}

Pattern types that DID NOT work: {failed_types}

Concepts they got wrong / struggled with:
{wrong_items}

Generate NEW adapted patterns that approach the material differently. If a type failed, don't use it again for that same content. For each pattern type you choose, generate exactly FOUR distinct variations (numbered "variation": 1-4) so the user can pick the one that sticks. Try simpler or more creative approaches."""

    # Budget for the number of types we expect back: the preferred types that
    # did not fail, or (if everything failed) one or two replacement types.
    failed = {t.lower() for t in req.failed_pattern_types}
    surviving = [p for p in req.preferences if p.type.lower() not in failed]
    n_types = max(len(surviving), 1) if req.preferences else 2
    budget = completion_budget(n_types)
    # The adaptation note needs a little extra room.
    budget = {"max_tokens": budget["max_tokens"] + 128, "min_tokens": budget["min_tokens"] + 64}

    raw = await client.chat_json(SYSTEM_PROMPT, user, temperature=0.4, **budget)

    note = DEFAULT_NOTE
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            candidate = data.get("adaptation_note")
            if isinstance(candidate, str) and candidate.strip():
                note = candidate.strip()
    except (json.JSONDecodeError, TypeError):
        pass

    patterns = parse_patterns(raw, default_label="Adapted Pattern", key="adapted_patterns")
    return AdaptPatternsResponse(adapted_patterns=patterns, adaptation_note=note)
