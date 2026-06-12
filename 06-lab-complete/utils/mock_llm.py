"""Offline mock LLM used by the deployment lab."""
import random
import time


MOCK_RESPONSES = {
    "default": [
        "This response came from the offline mock AI agent.",
        "The production agent received and processed your question.",
        "The service is healthy and the mock model is responding.",
    ],
    "docker": [
        "Docker packages an application and its dependencies into a portable container image."
    ],
    "deploy": [
        "Deployment makes an application available on infrastructure where users can reach it."
    ],
    "redis": [
        "Redis provides shared state so every agent instance can access the same conversation."
    ],
}


def ask(question: str, delay: float = 0.05) -> str:
    time.sleep(delay)
    lowered = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in lowered:
            return random.choice(responses)
    return random.choice(MOCK_RESPONSES["default"])
