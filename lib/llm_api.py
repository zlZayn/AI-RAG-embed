from openai import OpenAI


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
        extra_body = {}
        if self._thinking_mode:
            extra_body["thinking_mode"] = True

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            extra_body=extra_body if extra_body else None,
        )
        return response.choices[0].message.content
