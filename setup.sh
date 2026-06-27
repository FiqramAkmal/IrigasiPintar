#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"
SCHEMA_FILE="$ROOT_DIR/schema.sql"
VENV_DIR="$ROOT_DIR/.venv"
REQ_FILE="$ROOT_DIR/requirements.txt"

log() {
  printf '[setup] %s\n' "$1"
}

fail() {
  printf '[setup] ERROR: %s\n' "$1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Command '$1' not found."
}

load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    fail ".env not found at $ENV_FILE"
  fi

  set -a
  source "$ENV_FILE"
  set +a
}

check_env_vars() {
  local required_vars=(
    DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
    ADMIN_USERNAME ADMIN_PASSWORD
    JWT_SECRET
    MQTT_BROKER MQTT_PORT MQTT_TOPIC MQTT_DISEASE_TOPIC MQTT_COMMAND_TOPIC
    WEATHER_API_URL WEATHER_LATITUDE WEATHER_LONGITUDE
    MODEL_FILENAME
  )

  for var_name in "${required_vars[@]}"; do
    if [[ -z "${!var_name:-}" ]]; then
      fail "Environment variable '$var_name' is required in .env"
    fi
  done
}

setup_venv() {
  require_cmd python3

  [[ -f "$REQ_FILE" ]] || fail "requirements.txt not found"

  if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtual environment"
    python3 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  log "Installing Python dependencies"
  python -m pip install --upgrade pip
  python -m pip install -r "$REQ_FILE"
}

wait_for_db() {
  require_cmd mariadb

  log "Checking database connectivity"
  mariadb \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --user="$DB_USER" \
    --password="$DB_PASSWORD" \
    "$DB_NAME" \
    -e 'SELECT 1' >/dev/null
}

apply_schema() {
  [[ -f "$SCHEMA_FILE" ]] || fail "schema.sql not found"

  log "Applying latest schema.sql"
  mariadb \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --user="$DB_USER" \
    --password="$DB_PASSWORD" \
    "$DB_NAME" < "$SCHEMA_FILE"
}

seed_admin() {
  log "Seeding admin user"
  python "$ROOT_DIR/seed_admin.py"
}

verify_app() {
  log "Running Python compile check"
  python -m py_compile "$ROOT_DIR/main.py" "$ROOT_DIR/mqtt_handler.py" "$ROOT_DIR/db.py" "$ROOT_DIR/seed_admin.py" "$ROOT_DIR/simulasi.py"
}

main() {
  load_env
  check_env_vars
  setup_venv
  wait_for_db
  apply_schema
  seed_admin
  verify_app
  log "Setup complete"
  log "Activate venv: source .venv/bin/activate"
  log "Run app: python main.py"
}

main "$@"
