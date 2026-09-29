from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_id: str = ""
    client_secret: str = ""

    qq_api_base: str = "https://api.bot.qq.com"

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "clany_personal"
    db_user: str = "postgres"
    db_password: str = ""
    db_schema: str = "dmwd_for_owner"

    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_vision_model: str = ""
    ai_vision_api_key: str = ""
    ai_vision_base_url: str = ""
    ai_memory_max: int = 20
    ai_files_dir: str = "ai_files"
    public_base_url: str = ""

    bocha_api_key: str = ""

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    model_config = {"env_prefix": "QQ_BOT_", "env_file": ".env"}


settings = Settings()
