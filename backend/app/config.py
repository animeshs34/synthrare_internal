from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    secret_key: str = "change-me-to-at-least-32-characters-long"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Database
    database_url: str = "postgresql://synthrare:synthrare_dev@postgres:5432/synthrare"
    database_pool_size: int = 10

    # Queue
    redis_url: str = "redis://localhost:6379/0"

    # DO Spaces
    do_spaces_key: str = ""
    do_spaces_secret: str = ""
    do_spaces_endpoint: str = "https://nyc3.digitaloceanspaces.com"
    do_spaces_region: str = "nyc3"
    do_spaces_bucket: str = "synthrare-datasets"
    do_spaces_cdn_endpoint: str = ""

    # DO Gradient Inference
    do_gradient_api_key: str = ""
    do_gradient_inference_endpoint: str = ""

    # HuggingFace
    hf_token: str = ""
    hf_model_repo_finance: str = "synthrare/finance-ctgan"
    hf_model_repo_aviation: str = "synthrare/aviation-timegan"
    hf_model_repo_healthcare: str = "synthrare/healthcare-ctgan"

    # Storage
    use_local_storage: bool = True
    local_storage_path: str = "./data/uploads"

    # Frontend
    next_public_api_url: str = "http://localhost:8000"
    next_public_app_url: str = "http://localhost:3000"


settings = Settings()
