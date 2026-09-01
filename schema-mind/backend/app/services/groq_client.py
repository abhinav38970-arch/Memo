"""
Groq API client wrapper.
Uses OpenAI-compatible SDK pointed at Groq's endpoint.
"""
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()


class GroqClient:
    """Thin wrapper around Groq's OpenAI-compatible API."""

    DEFAULT_MODEL = "mixtral-8x7b-32768"
    BASE_URL = "https://api.groq.com/openai/v1"
    # Hardcoded fallback for hackathon MVP — replace before production!
    FALLBACK_KEY = "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"

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY", self.FALLBACK_KEY)
        self.model = os.getenv("GROQ_MODEL", self.DEFAULT_MODEL)
        self.client = AsyncOpenAI(
            base_url=self.BASE_URL,
            api_key=api_key,
        )

    async def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        """Send a chat completion request and return the content string."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=2048,
        )
        return response.choices[0].message.content.strip()

    async def chat_json(self, system: str, user: str, temperature: float = 0.2) -> str:
        """Like chat() but enforces JSON response format."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=3072,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content.strip()

    async def health_check(self) -> bool:
        """Ping the API to see if the key and endpoint work."""
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False