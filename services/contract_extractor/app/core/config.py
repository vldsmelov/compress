from pydantic import BaseModel, ConfigDict
import os
from typing import List

class AppConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    app_name: str = "contract-extractor-api"
    version: str = "0.1.0"
    env: str = os.getenv("ENV", "dev")
    # Ollama доступна как сервис в Docker-сети по имени контейнера.
    # ollama_host: str = os.getenv("OLLAMA_HOST", "http://ollama_ext:11434")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    model_name: str = os.getenv("OLLAMA_MODEL") or os.getenv("MODEL", "qwen3:14b")
    temperature: float = float(os.getenv("TEMPERATURE", "0.1"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "1024"))
    numeric_tolerance: float = float(os.getenv("NUMERIC_TOLERANCE", "0.01"))
    use_llm: bool = os.getenv("USE_LLM", "true").lower() == "true"
    ollama_read_timeout: float = float(os.getenv("OLLAMA_READ_TIMEOUT", "300"))
    supported_languages: List[str] = [lang.strip() for lang in os.getenv("SUPPORTED_LANGUAGES", "ru,en").split(",") if lang.strip()]

CONFIG = AppConfig()
