import json
import logging
import os
import time
from functools import lru_cache

import boto3
import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Coditude assessment API", docs_url=None, redoc_url=None)
logger = logging.getLogger("uvicorn.error")

@lru_cache(maxsize=1)
def secrets_client():
    return boto3.client("secretsmanager")

@lru_cache(maxsize=2)
def database_credentials(cache_window: int):
    # Refresh within 60 seconds; never log the returned secret.
    arn = os.environ.get("DB_SECRET_ARN")
    if arn:
        return json.loads(secrets_client().get_secret_value(SecretId=arn)["SecretString"])
    if os.environ.get("APP_ENV") != "local":
        raise RuntimeError("DB_SECRET_ARN is required outside local development")
    return {"username": os.environ["DB_USER"], "password": os.environ["DB_PASSWORD"]}

def check_database():
    credentials = database_credentials(int(time.time() // 60))
    options = dict(host=os.environ["DB_HOST"], port=int(os.getenv("DB_PORT", "5432")),
                   dbname=os.getenv("DB_NAME", "assessment"), user=credentials["username"],
                   password=credentials["password"], connect_timeout=3,
                   sslmode="disable" if os.getenv("APP_ENV") == "local" else "verify-full")
    if options["sslmode"] == "verify-full":
        options["sslrootcert"] = os.getenv("DB_CA_PATH", "/app/certs/global-bundle.pem")
    with psycopg.connect(**options) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            if cursor.fetchone() != (1,):
                raise RuntimeError("Database probe failed")

@app.get("/api/health")
def health():
    # Liveness stays independent of shared-database outages.
    return {"status": "ok"}

@app.get("/api/ready")
def ready():
    try:
        check_database()
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.warning("Database readiness failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unavailable"})
