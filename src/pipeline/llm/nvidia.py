import logging
import time

from openai import OpenAI

from pipeline.llm.config import (
    get_llm_api_key,
    get_llm_base_url,
    get_llm_model,
)
from pipeline.llm.debug import log_llm_call, log_llm_response

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

        self._call_counts: dict[str, int] = {}

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        max_tokens: int = 16384,
        temperature: float = 1.0,
        top_p: float = 0.95,
        enable_thinking: bool = True,
        stage: str = "unknown",
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

        self._call_counts[stage] = self._call_counts.get(stage, 0) + 1
        call_number = self._call_counts[stage]

        request_payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "extra_body": {
                "chat_template_kwargs": {
                    "enable_thinking": enable_thinking,
                }
            },
        }

        call_id = log_llm_call(
            stage=stage,
            model=self.model,
            system_prompt=system_prompt,
            user_prompt=prompt,
            evidence="",
            request_payload=request_payload,
            call_number=call_number,
        )

        start_time = time.perf_counter()
        error = None
        response_text = ""
        success = False

        try:
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
                },
            )

            choice = response.choices[0]

            logger.debug(
                "LLM response: finish_reason=%s usage=%s",
                choice.finish_reason,
                response.usage,
            )

            response_text = response.choices[0].message.content or ""
            success = True

        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            log_llm_response(
                call_id=call_id,
                stage=stage,
                model=self.model,
                response_text=response_text,
                duration_ms=duration_ms,
                success=success,
                error=error,
            )

        return response_text