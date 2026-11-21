"""Application configuration loaded from environment (.env)."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    admin_api_token: str = "change_me_admin_token"
    operator_api_token: str = ""  # optional: operator role (admin always allowed)
    # CORS allowlist (comma-separated). Jangan "*" di production.
    cors_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+psycopg2://middleware:change_me_db@db:5432/middleware"

    # Validation
    use_hapi_validator: bool = False
    hapi_validator_url: str = "http://hapi-validator:3500"

    # OpenMRS
    openmrs_enabled: bool = True
    openmrs_mode: str = "mock"
    openmrs_fhir_base_url: str = "http://openmrs:8080/openmrs/ws/fhir2/R4"
    openmrs_auth_type: str = "basic"
    openmrs_username: str = "admin"
    openmrs_password: str = "Admin123"
    openmrs_mock_url: str = "http://mock-ehr:8100/openmrs"

    # OpenEMR
    openemr_enabled: bool = True
    openemr_mode: str = "mock"
    openemr_fhir_base_url: str = "http://openemr/apis/default/fhir"
    openemr_auth_type: str = "oauth2_client_credentials"
    openemr_client_id: str = ""
    openemr_client_secret: str = ""
    openemr_token_url: str = ""
    openemr_mock_url: str = "http://mock-ehr:8100/openemr"

    # SATUSEHAT
    satusehat_enabled: bool = True
    satusehat_mode: str = "mock"
    satusehat_fhir_base_url: str = "https://api-satusehat-stg.dto.kemkes.go.id/fhir-r4/v1"
    satusehat_client_id: str = ""
    satusehat_client_secret: str = ""
    satusehat_token_url: str = "https://api-satusehat-stg.dto.kemkes.go.id/oauth2/v1/accesstoken?grant_type=client_credentials"
    satusehat_org_id: str = ""
    satusehat_mock_url: str = "http://mock-satusehat:8200/fhir-r4/v1"
    # Prasyarat & default untuk jalur otomatis ke SATUSEHAT (sandbox/production)
    satusehat_practitioner_ihs: str = "10009880010"
    satusehat_location_id: str = ""          # kosong -> resolve/create otomatis
    satusehat_default_icd10: str = "J06.9"
    satusehat_default_icd10_display: str = "Acute upper respiratory infection, unspecified"
    # SSRME (Rekam Medis Elektronik viewing) base, e.g. sandbox .../ssrme/v2/ntl
    ssrme_base_url: str = "https://api-satusehat-stg.dto.kemkes.go.id/ssrme/v2/ntl"
    ssrme_enabled: bool = True

    # Scheduler / worker
    poll_interval_seconds: int = 30
    reconcile_interval_seconds: int = 120
    worker_poll_seconds: int = 5
    retry_max_attempts: int = 5
    # Hardening
    payload_retention_on_success: bool = True   # clear stored payload after success (privacy)
    rate_limit_per_minute: int = 120            # max admin API requests/min per IP (0 = disabled)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
