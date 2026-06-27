from __future__ import annotations

import bcrypt
import os
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue

        key, value = entry.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


BASE_DIR = Path(__file__).resolve().parent
load_env_file(BASE_DIR / ".env")

from db import insert_user, user_exists  # noqa: E402

username = os.environ.get("ADMIN_USERNAME", "admin")
password = os.environ.get("ADMIN_PASSWORD", "admin123")

if user_exists(username):
    print(f"User '{username}' already exists.")
else:
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user_id = insert_user(username, password_hash, "admin", 1)
    print(f"Created admin user '{username}' with id {user_id}.")
