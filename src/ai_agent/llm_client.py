import json
import urllib.request


URL = "http://127.0.0.1:8080/v1/chat/completions"


def query_llm(messages, tools=None, tool_choice="auto"):
    payload = {
        "model": "Agents-A1-4B",
        "messages": messages,
        "temperature": 0.1,
    }

    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]
