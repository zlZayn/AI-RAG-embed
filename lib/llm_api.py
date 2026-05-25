import time

from openai import OpenAI

MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]


class LlmApi:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.3,
        thinking_mode: bool = False,
    ):
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature
        self._thinking_mode = thinking_mode

    def generate(self, messages: list[dict]) -> str:
        return "".join(self.generate_stream(messages))

    def generate_stream(self, messages: list[dict]):
        extra_body = {}
        if self._thinking_mode:
            extra_body["thinking_mode"] = True

        for attempt in range(MAX_RETRIES):
            try:
                stream = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=self._temperature,
                    extra_body=extra_body if extra_body else None,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield delta.content
                return
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    print(
                        f"[retry {attempt + 1}/{MAX_RETRIES}] API call failed, retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    print(f"[error] API call failed: {e}")
                    raise
