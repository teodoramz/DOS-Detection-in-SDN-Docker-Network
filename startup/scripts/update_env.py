import pandas as pd
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import os

DDOS_DETECTION_HOME = Path(os.getenv("DDOS_DETECTION_HOME", Path(__file__).resolve().parent))

containers_csv_path = DDOS_DETECTION_HOME / "startup/files/input/containers.csv"
template_path = DDOS_DETECTION_HOME / "startup/templates/env.j2"
output_path = DDOS_DETECTION_HOME / "startup/files/output/.env"

def get_ip_map(csv_path):
    df = pd.read_csv(csv_path)
    ip_map = {}
    for _, row in df.iterrows():
        name = row["Name"].strip().lower()
        for sw in ["Sw1", "Sw2", "Sw3", "Sw4", "Sw5"]:
            val = str(row.get(sw, "")).strip()
            if val and val != "-":
                ip_map[f"{name}_{sw.lower()}_ip"] = val.split("/")[0]
    return ip_map


def main():
    ip_map = get_ip_map(containers_csv_path)

    for k, v in ip_map.items():
        print(f"  {k} = {v}")

    env = Environment(loader=FileSystemLoader(Path(template_path).parent))
    template = env.get_template(Path(template_path).name)

    rendered = template.render(ip_map)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(rendered)

    print(f"\nEnv file generated: {output_path}")


if __name__ == "__main__":
    main()
