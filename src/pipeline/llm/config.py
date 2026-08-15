import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
DEFAULT_PROVIDER = "nvidia"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_WORKER_CONCURRENCY = 1


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER)


def get_llm_model() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


def get_llm_api_key() -> str | None:
    return os.getenv("NVIDIA_API_KEY")


def get_llm_base_url() -> str:
    return os.getenv("LLM_BASE_URL", DEFAULT_BASE_URL)


def get_worker_concurrency() -> int:
    value = os.getenv("WORKER_CONCURRENCY")
    if value is None:
        return DEFAULT_WORKER_CONCURRENCY
    try:
        concurrency = int(value)
    except ValueError:
        raise ValueError(f"WORKER_CONCURRENCY must be an integer, got: {value}")
    if concurrency < 1:
        raise ValueError(f"WORKER_CONCURRENCY must be a positive integer, got: {concurrency}")
    return concurrency