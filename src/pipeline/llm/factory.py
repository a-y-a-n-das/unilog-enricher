from pipeline.llm.client import LLMClient
from pipeline.llm.config import get_llm_provider
from pipeline.llm.nvidia import NVIDIAClient


def get_llm_client() -> LLMClient:
    provider = get_llm_provider().lower()

    if provider == "nvidia":
        return NVIDIAClient()

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )