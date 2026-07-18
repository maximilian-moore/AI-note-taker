"""Central configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # auth
    device_pairing_token: str = "change-me"
    dashboard_password: str = "change-me"

    # engines: "cloud" | "local"
    transcribe_engine: str = "cloud"
    llm_engine: str = "cloud"

    # cloud keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # local engines (phase 3)
    whisper_model: str = "base"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # behaviour
    languages: str = "de,en"
    data_dir: str = "/data"
    keep_audio: bool = True
    max_meeting_minutes: int = 120


settings = Settings()
