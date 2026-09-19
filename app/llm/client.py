from google import genai

from app.config import settings


def get_client() -> genai.Client:
    """Create a Gemini client; the caller must close it after use."""
    if not settings.google_api_key or not settings.google_api_key.get_secret_value():
        raise ValueError("Set GOOGLE_API_KEY in .env before using the Google API")
    return genai.Client(
        api_key=settings.google_api_key.get_secret_value(),
    )
