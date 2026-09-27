from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_id: str = ""
    client_secret: str = ""

    qq_api_base: str = "https://api.bot.qq.com"

    model_config = {"env_prefix": "QQ_BOT_", "env_file": ".env"}


settings = Settings()
