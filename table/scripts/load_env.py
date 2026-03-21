from pathlib import Path
import os


def load_env_from_file(env_path):
    env_path = Path(env_path)
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                is_valid = line.strip() and not line.strip().startswith("#") \
                    and "=" in line

                if is_valid:
                    k, v = line.strip().split("=", 1)
                    os.environ.setdefault(k, v)
