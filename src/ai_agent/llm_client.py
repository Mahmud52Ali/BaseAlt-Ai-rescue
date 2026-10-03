import json
import urllib.error
import urllib.request

from .selector_model.config import load_settings


_settings = None


def configure_llm():
    global _settings
    _settings = load_settings()
    return _settings


def query_llm(messages, tools=None, tool_choice="auto"):
    settings = _settings if _settings is not None else configure_llm()
    payload = {
        "model": settings["model"],
        "messages": messages,
        "temperature": 0.1,
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    headers = {"Content-Type": "application/json"}
    if settings["api_key"]:
        headers["Authorization"] = f"Bearer {settings['api_key']}"

    request = urllib.request.Request(
        settings["url"],
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=settings["timeout_seconds"]) as response:
            result = json.loads(response.read().decode("utf-8"))
        message = result["choices"][0]["message"]
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"LLM API returned HTTP {error.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Cannot connect to the configured LLM API") from None
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        raise RuntimeError("LLM API returned an invalid chat/completions response") from None

    if not isinstance(message, dict):
        raise RuntimeError("LLM API response does not contain a message")
    return message
