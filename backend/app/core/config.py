import os, secrets, logging

log = logging.getLogger("mediwatch")


class Settings:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./mediwatch.db")
        key = os.getenv("SECRET_KEY", "")
        if not key:
            key = secrets.token_urlsafe(48)
            log.warning("SECRET_KEY not set: using a random key (logins reset on restart). Set it in .env.")
        self.secret_key = key
        self.token_minutes = int(os.getenv("TOKEN_MINUTES", "480"))
        self.openfda_api_key = os.getenv("OPENFDA_API_KEY") or None
        self.cors_origins = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o]
        self.model_dir = os.getenv("MODEL_DIR", "models")


settings = Settings()
