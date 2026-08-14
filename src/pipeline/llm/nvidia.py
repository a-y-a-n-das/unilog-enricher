import logging

from openai import OpenAI

from pipeline.llm.config import (
    get_llm_api_key,
    get_llm_base_url,
    get_llm_model,
)

logger = logging.getLogger(__name__)


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
            max_retries=5,
        )

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 16384,
        temperature: float = 1.0,
        top_p: float = 0.95,
        enable_thinking: bool = True,
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
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            extra_body={
                "chat_template_kwargs": {
                "enable_thinking": enable_thinking,
            }
            }
        )

        choice = response.choices[0]

        logger.debug(
            "LLM response: finish_reason=%s usage=%s",
            choice.finish_reason,
            response.usage,
        )

        return response.choices[0].message.content or ""