import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(ROOT_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PROJECT_NAME: str = "HydraControl Commercial IoT Platform"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "hydracontrol_super_secret_development_jwt_key_change_in_prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./hydracontrol.db"
    SYNC_DATABASE_URL: str = "sqlite:///./hydracontrol.db"

    @field_validator("DATABASE_URL", "SYNC_DATABASE_URL", mode="after")
    @classmethod
    def anchor_sqlite_database_path(cls, v: str) -> str:
        """Ensure relative SQLite paths always resolve to the master workspace database."""
        if isinstance(v, str) and v.startswith("sqlite"):
            import re
            match = re.match(r"^(sqlite(?:\+[a-z0-9_]+)?:\/{2,3})(.*)$", v)
            if match:
                dialect_prefix = match.group(1).split("://")[0] + ":///"
                path_part = match.group(2).replace("\\", "/")
                # If already absolute Windows (C:/) or POSIX (/path)
                if re.match(r"^[a-zA-Z]:", path_part):
                    return f"{dialect_prefix}{path_part}"
                elif path_part.startswith("/"):
                    clean_win = re.sub(r"^\/([a-zA-Z]:)", r"\1", path_part)
                    return f"{dialect_prefix}{clean_win}"
                else:
                    clean_rel = re.sub(r"^\.\/", "", path_part)
                    if not clean_rel:
                        clean_rel = "hydracontrol.db"
                    if os.path.basename(clean_rel) == "hydracontrol.db":
                        abs_path = os.path.abspath(os.path.join(ROOT_DIR, "hydracontrol.db")).replace("\\", "/")
                    else:
                        abs_path = os.path.abspath(os.path.join(ROOT_DIR, clean_rel)).replace("\\", "/")
                    return f"{dialect_prefix}{abs_path}"
        return v

    # MQTT
    MQTT_BROKER_HOST: str = "localhost"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: str = ""
    MQTT_PASSWORD: str = ""
    MQTT_KEEPALIVE: int = 60
    MQTT_CLIENT_ID: str = "hydracontrol_backend_gateway"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173"
    ]

    # WebSocket
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 15

    # Safety & Watchdogs
    DEFAULT_COMMAND_TIMEOUT_SECONDS: int = 10
    HEARTBEAT_STALE_THRESHOLD_SECONDS: int = 30
    HEARTBEAT_OFFLINE_THRESHOLD_SECONDS: int = 60


settings = Settings()
