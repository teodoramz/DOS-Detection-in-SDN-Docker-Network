import re
from pathlib import Path
import json
import os

DDOS_DETECTION_HOME = Path(os.getenv("DDOS_DETECTION_HOME", Path(__file__).resolve().parent))

env_file_path = DDOS_DETECTION_HOME / "startup/files/output/.env"
output_json_path = DDOS_DETECTION_HOME / "startup/files/output/jinja_vars.json"

def parse_env_file(env_path):
    env_vars = {}

    for line in Path(env_path).read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        match = re.match(r"^([A-Za-z0-9_]+)=(.*)$", line)
        if not match:
            continue

        key, value = match.groups()

        value = value.strip().strip('"').strip("'")

        key = key.lower()

        env_vars[key] = value

    return env_vars


def main():
    print(f"DDOS_DETECTION_HOME = {DDOS_DETECTION_HOME}")

    if not env_file_path.exists():
        raise FileNotFoundError(f"File not existing {env_file_path}")

    env_vars = parse_env_file(env_file_path)

    for k, v in env_vars.items():
        print(f"{k} = {v}")

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(env_vars, indent=2))
    print(f"\nJson Exported: {output_json_path}")

if __name__ == "__main__":
    main()
