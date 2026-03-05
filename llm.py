"""
LLM - Simple wrapper for LLM API calls.
No abstractions, no retry, no async. Just call and return.
"""

import os
from pathlib import Path


def _load_env():
    """Load .env file from project root into os.environ."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_env()  # Run at import time

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
}


def call_llm(prompt: str, provider: str = "anthropic", model: str = None,
             api_key: str = None, max_tokens: int = 1024) -> str:
    """
    Call an LLM and return response text.
    Never raises - returns error string on failure.
    """
    if provider == "stub":
        return f"[Stub response for {len(prompt)} char prompt]"

    model = model or DEFAULT_MODELS.get(provider, "unknown")

    try:
        if provider == "anthropic":
            return _call_anthropic(prompt, model, api_key, max_tokens)
        elif provider == "openai":
            return _call_openai(prompt, model, api_key, max_tokens)
        else:
            return f"[LLM Error: Unknown provider '{provider}']"
    except Exception as e:
        return f"[LLM Error: {e}]"


def _call_anthropic(prompt: str, model: str, api_key: str, max_tokens: int) -> str:
    import anthropic
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return "[LLM Error: No ANTHROPIC_API_KEY]"

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_openai(prompt: str, model: str, api_key: str, max_tokens: int) -> str:
    import openai
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        return "[LLM Error: No OPENAI_API_KEY]"

    client = openai.OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def make_llm_fn(provider: str = "anthropic", model: str = None, api_key: str = None) -> callable:
    """Return a callable matching Capsule's llm_fn interface."""
    def llm_fn(prompt: str, **kwargs) -> str:
        return call_llm(prompt, provider=provider, model=model, api_key=api_key, **kwargs)
    return llm_fn


if __name__ == "__main__":
    # Test stub provider
    result = call_llm("Hello world", provider="stub")
    print(f"Stub: {result}")

    # Test missing API key handling
    result = call_llm("Hello", provider="anthropic", api_key=None)
    if "ANTHROPIC_API_KEY" in os.environ:
        print(f"Anthropic: {result[:50]}...")
    else:
        print(f"Anthropic (no key): {result}")

    # Test make_llm_fn
    stub_fn = make_llm_fn(provider="stub")
    print(f"make_llm_fn: {stub_fn('Test prompt')}")
