"""
Pattern generation service.
Takes raw text + user preferences → returns memory-aid patterns in JSON.
"""
import json
from typing import List
from app.models.schemas import PatternPreference, GeneratedPattern, GeneratePatternsResponse
from app.services.groq_client import GroqClient


SYSTEM_PROMPT = """You are SchemaMind, an AI that transforms educational text into memory-optimized patterns.
You analyze text the user needs to memorize and generate creative memory aids in formats that work for THEM.

Your output MUST be valid JSON matching this exact structure:
{
  "patterns": [
    {
      "type": "acronym" | "acrostic" | "analogy" | "number" | "story" | "custom",
      "label": "Short descriptive label",
      "content": "The full pattern/explanation"
    }
  ]
}

RULES:
1. Generate EXACTLY ONE pattern per preferred type the user selected (no more, no less).
2. Each pattern must be genuinely useful for memorizing the key concepts in the text.
3. For "custom" types, follow the user's description of how they memorize best.
4. Be creative but accurate — don't invent facts.
5. Keep patterns concise (1-4 sentences each).
6. The content should be something the user can actually recall from memory. If the user picks custom preference, adapt to their style exactly."""


def _build_user_prompt(text: str, preferences: List[PatternPreference]) -> str:
    prefs_lines = []
    for p in preferences:
        if p.type == "custom":
            prefs_lines.append(f"- Custom: {p.custom_description}")
        else:
            prefs_lines.append(f"- {p.type}")
    prefs_str = "\n".join(prefs_lines)

    return f"""Here is the text the user needs to memorize:
---START TEXT---
{text}
---END TEXT---

The user wants memory patterns in these formats:
{prefs_str}

Generate ONE pattern for each format requested. Return as JSON."""


async def generate_patterns(
    text: str,
    preferences: List[PatternPreference],
) -> GeneratePatternsResponse:
    client = GroqClient()
    user = _build_user_prompt(text, preferences)
    raw = await client.chat_json(SYSTEM_PROMPT, user)

    try:
        data = json.loads(raw)
        patterns_data = data.get("patterns", [])
    except (json.JSONDecodeError, KeyError):
        # fallback: try to salvage
        patterns_data = []

    patterns = []
    for p in patterns_data:
        patterns.append(GeneratedPattern(
            type=p.get("type", "custom"),
            label=p.get("label", "Memory Pattern"),
            content=p.get("content", ""),
        ))

    return GeneratePatternsResponse(patterns=patterns)