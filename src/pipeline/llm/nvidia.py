from openai import OpenAI

from pipeline.llm.config import (
    get_llm_api_key,
    get_llm_base_url,
    get_llm_model,
)


class NVIDIAClient:
    def __init__(self) -> None:
        api_key = get_llm_api_key()

        if not api_key:
            raise ValueError(
                "NVIDIA_API_KEY is not set"
            )

        self.model = get_llm_model()

        self.client = OpenAI(
            base_url=get_llm_base_url(),
            api_key=api_key,
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
    ) -> str:
        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=1.0,
            top_p=0.95,
            max_tokens=16384,
        )

        return response.choices[0].message.content or ""