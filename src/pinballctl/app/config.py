"""Default Flask configuration values (override with environment vars)."""

# pinballctl/app/config.py

# Flask secret key (sessions). Override in env for production.
SECRET_KEY = "dev-not-secret-change-me"

# Branding / title
APP_TITLE = "pinballCTL"

# Auth toggle (True/False). Env PINBALLCTL_AUTH can also override.
AUTH_ENABLED = True

# Credentials (choose ONE of PASSWORD or PASSWORD_HASH).
# Default user if not set: "admin"
AUTH_USER = "admin"

# DEV ONLY: plain text password. Prefer using AUTH_PASSWORD_HASH in prod.
AUTH_PASSWORD = "password"

# PROD: Werkzeug pbkdf2 hash string, e.g.:
# from werkzeug.security import generate_password_hash
# AUTH_PASSWORD_HASH = generate_password_hash("your-strong-pass")
AUTH_PASSWORD_HASH = None

# Default remote firmware manifest URL (override via env PINBALLCTL_REMOTE_FIRMWARE_URL)
REMOTE_FIRMWARE_URL = "http://127.0.0.1:8888/api/firmware/versions"

# External docs site URL used by the top navigation Docs button.
DOCS_URL = "https://docs.pinballctl.com"
