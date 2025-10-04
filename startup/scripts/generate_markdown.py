import pandas as pd
from pathlib import Path
import os

DDOS_DETECTION_HOME = Path(os.getenv("DDOS_DETECTION_HOME", Path(__file__).resolve().parent))

hosts_csv_path = DDOS_DETECTION_HOME / "startup/files/input/hosts.csv"
switches_csv_path = DDOS_DETECTION_HOME / "startup/files/input/switches.csv"
containers_csv_path = DDOS_DETECTION_HOME / "startup/files/input/containers.csv"

output_markdown_path = DDOS_DETECTION_HOME / "startup/files/output/network_inventory.md"

def csv_to_markdown_table(df: pd.DataFrame, title: str) -> str:
    markdown = f"# {title}\n"
    markdown += "| " + " | ".join(df.columns) + " |\n"
    markdown += "|" + "|".join(["-" * len(col) for col in df.columns]) + "|\n"
    for _, row in df.iterrows():
        markdown += "| " + " | ".join(str(v) for v in row.values) + " |\n"
    markdown += "\n"
    return markdown


def main():
    for path in [hosts_csv_path, switches_csv_path, containers_csv_path]:
        if not Path(path).exists():
            raise FileNotFoundError(f"Input file not existing: {path}")

    hosts = pd.read_csv(hosts_csv_path)
    switches = pd.read_csv(switches_csv_path)
    containers = pd.read_csv(containers_csv_path)

    markdown_output = ""
    markdown_output += csv_to_markdown_table(hosts, "Hosts")
    markdown_output += csv_to_markdown_table(switches, "Switches + Ryu")
    markdown_output += csv_to_markdown_table(containers, "Containers")

    Path(output_markdown_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_markdown_path, "w") as f:
        f.write(markdown_output)

    print(f"Markdown generated successfully: {output_markdown_path}")
if __name__ == "__main__":
    main()
