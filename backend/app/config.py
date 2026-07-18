"""Central configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # auth
    device_pairing_token: str = "change-me"
    dashboard_password: str = "change-me"

    # engines: "cloud" | "mock"
    # Default is "mock" so the whole stack runs end-to-end with NO API keys.
    # Flip to "cloud" (and set the keys below) for real transcription/enrichment.
    transcribe_engine: str = "mock"
    llm_engine: str = "mock"

    # cloud keys
    openai_api_key: str = ""
    openai_transcribe_model: str = "whisper-1"
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

    # how many recent items the device browses
    device_list_limit: int = 20

    @property
    def language_hints(self) -> list[str]:
        return [x.strip() for x in self.languages.split(",") if x.strip()]


settings = Settings()
