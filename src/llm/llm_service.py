
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

FOUNDRY_API_KEY = os.getenv("FOUNDRY_API_KEY")
FOUNDRY_ENDPOINT = os.getenv("FOUNDRY_ENDPOINT")
FOUNDRY_MODEL = os.getenv("FOUNDRY_MODEL", "gpt-4.1-nano")


# ============================================================
# AZURE AI FOUNDRY CLIENT
# ============================================================

def get_llm_client():
    """Create and return the Azure AI Foundry OpenAI client."""

    if not FOUNDRY_API_KEY:
        raise ValueError("FOUNDRY_API_KEY is missing from .env")

    if not FOUNDRY_ENDPOINT:
        raise ValueError("FOUNDRY_ENDPOINT is missing from .env")

    return OpenAI(
        api_key=FOUNDRY_API_KEY,
        base_url=FOUNDRY_ENDPOINT
    )


# ============================================================
# SHARED LLM RESPONSE
# ============================================================

def generate_response(prompt, system_message=None):
    """
    Generate a response using the configured Azure AI Foundry model.
    """

    client = get_llm_client()

    messages = []

    if system_message:
        messages.append({
            "role": "system",
            "content": system_message
        })

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = client.chat.completions.create(
        model=FOUNDRY_MODEL,
        messages=messages,
        temperature=0.2
    )

    return response.choices[0].message.content.strip()


# ============================================================
# CONNECTION TEST
# ============================================================

def test_llm_connection():
    """Verify that the configured model responds."""

    response = generate_response(
        prompt="Reply with exactly: Azure AI Foundry connection successful.",
        system_message="You are a helpful AI assistant."
    )

    return response


if __name__ == "__main__":

    print("=" * 60)
    print("AZURE AI FOUNDRY CONNECTION TEST")
    print("=" * 60)

    try:
        result = test_llm_connection()

        print("\nModel:", FOUNDRY_MODEL)
        print("Response:", result)
        print("\nLLM connection test completed.")

    except Exception as error:
        print("\nLLM CONNECTION FAILED")
        print(error)
