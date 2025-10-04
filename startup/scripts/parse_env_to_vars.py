import re
import csv
import json
import os
from pathlib import Path


DDOS_DETECTION_HOME = Path(os.getenv("DDOS_DETECTION_HOME", Path(__file__).resolve().parent))

env_file_path = DDOS_DETECTION_HOME / "startup/files/output/.env"
output_json_path = DDOS_DETECTION_HOME / "startup/variables/jinja_vars.json"

containers_csv_path = DDOS_DETECTION_HOME / "startup/files/input/containers.csv"
hosts_csv_path = DDOS_DETECTION_HOME / "startup/files/input/hosts.csv"
switches_csv_path = DDOS_DETECTION_HOME / "startup/files/input/switches_ryu.csv"

def safe_read_text(path: Path) -> str:
    try:
        return path.read_text()
    except Exception:
        return ""

def parse_env_file(env_path):
    env_vars = {}
    content = safe_read_text(env_path)
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_]+)=(.*)$", line)
        if not m:
            continue
        key, value = m.groups()
        value = value.strip().strip('"').strip("'")
        env_vars[key.lower()] = value
    return env_vars

def read_csv_dict(path: Path):
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as f:
        try:
            return list(csv.DictReader(f))
        except Exception:
            return []

def normalize_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', name.lower())

def build_containers_map(rows):
    containers_list = []
    container_ip_map = {}

    for r in rows:
        raw_name = (r.get("Name") or r.get("name") or "").strip()
        if not raw_name:
            continue
        name = normalize_name(raw_name)
        entry = {"name": raw_name}

        # mgmt ip
        mgmt = (r.get("Mgmt IP") or r.get("Mgmt_IP") or r.get("Mgmt ip") or r.get("mgmt ip") or "").strip()
        if mgmt and mgmt != "-":
            mgmt_ip = mgmt.split("/")[0]
            entry["mgmt_ip"] = mgmt_ip
            container_ip_map[f"{name}_mgmt_ip"] = mgmt_ip

        # sw1..sw5
        for sw in ("Sw1", "Sw2", "Sw3", "Sw4", "Sw5"):
            val = (r.get(sw) or r.get(sw.lower()) or "").strip()
            if val and val != "-":
                ip = val.split("/")[0]
                entry[f"{sw.lower()}"] = ip
                container_ip_map[f"{name}_{sw.lower()}_ip"] = ip

        containers_list.append(entry)

    return containers_list, container_ip_map

def build_hosts_map(rows):
    hosts_list = []
    host_map = {}
    for r in rows:
        raw_name = (r.get("Name") or r.get("name") or "").strip()
        if not raw_name:
            continue
        name = normalize_name(raw_name)
        entry = {"name": raw_name}
        ip_default = (r.get("Ip address default interface") or r.get("Ip address default") or r.get("ip") or "").strip()
        mgmt = (r.get("Mgmt IP") or r.get("Mgmt_IP") or "").strip()
        if ip_default and ip_default != "-":
            entry["ip"] = ip_default.split("/")[0]
            host_map[f"{name}_ip"] = entry["ip"]
        if mgmt and mgmt != "-":
            entry["mgmt_ip"] = mgmt.split("/")[0]
            host_map[f"{name}_mgmt_ip"] = entry["mgmt_ip"]
        hosts_list.append(entry)
    return hosts_list, host_map

def build_switches_map(rows):
    switches_list = []
    switches_map = {}
    for r in rows:
        raw_name = (r.get("Name") or r.get("name") or "").strip()
        if not raw_name:
            continue
        name = normalize_name(raw_name)
        entry = {"name": raw_name}

        host = (r.get("Host") or r.get("host") or "").strip()
        local_subnet = (r.get("Local Subnet") or r.get("Local_Subnet") or r.get("local subnet") or "").strip()
        internal_gateway = (r.get("Internal Gateway") or r.get("Internal_Gateway") or "").strip()
        mgmt = (r.get("Mgmt IP") or r.get("Mgmt_IP") or r.get("Mgmt ip") or "").strip()
        if host:
            entry["host"] = host
            switches_map[f"{name}_host"] = host
        if local_subnet:
            entry["local_subnet"] = local_subnet
            switches_map[f"{name}_local_subnet"] = local_subnet
        if internal_gateway:
            entry["internal_gateway"] = internal_gateway.split("/")[0] if "/" in internal_gateway else internal_gateway
            switches_map[f"{name}_internal_gateway"] = switches_map.get(f"{name}_internal_gateway", entry.get("internal_gateway"))
        if mgmt and mgmt != "-":
            entry["mgmt_ip"] = mgmt.split("/")[0]
            switches_map[f"{name}_mgmt_ip"] = entry["mgmt_ip"]
        switches_list.append(entry)
    return switches_list, switches_map

def main():

    if not env_file_path.exists():
        raise FileNotFoundError(f"File not existing {env_file_path}")
    env_vars = parse_env_file(env_file_path)

    containers_rows = read_csv_dict(containers_csv_path)
    hosts_rows = read_csv_dict(hosts_csv_path)
    switches_rows = read_csv_dict(switches_csv_path)

    containers_list, container_ip_map = build_containers_map(containers_rows)
    hosts_list, host_map = build_hosts_map(hosts_rows)
    switches_list, switches_map = build_switches_map(switches_rows)

    jinja_context = {}
    jinja_context.update(env_vars)
    jinja_context.update(host_map)
    jinja_context.update(switches_map)
    jinja_context.update(container_ip_map)

    jinja_context["containers"] = containers_list
    jinja_context["hosts"] = hosts_list
    jinja_context["switches"] = switches_list

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(jinja_context, indent=2))


    sample_keys = list(jinja_context.keys())[:60]
    for k in sample_keys:
        if k in ("containers", "hosts", "switches"):
            print(f"{k} = <list: {len(jinja_context[k])} items>")
        else:
            print(f"{k} = {jinja_context[k]}")
    print(f"\nJSON exported: {output_json_path}")

if __name__ == "__main__":
    main()
