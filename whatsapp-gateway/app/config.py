from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuración del gateway. En producción, META_ACCESS_TOKEN y
    META_APP_SECRET vienen de Google Secret Manager (Arquitectura v1.2,
    sección 4 "Seguridad"), nunca hardcodeados ni versionados.
    """

    internal_service_token: str = "dev-only-shared-secret-change-me"
    django_internal_url: str = "http://django-api:8000"

    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_webhook_verify_token: str = "dev-only-verify-token-change-me"
    meta_app_secret: str = ""
    meta_api_version: str = "v20.0"

    class Config:
        env_file = ".env"


settings = Settings()
