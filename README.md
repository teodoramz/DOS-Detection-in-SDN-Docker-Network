# Multi-Layer DDoS Detection in a Containerized SDN

A three-layer software-defined network, built entirely from Docker containers
across two hosts, that captures traffic per layer, classifies it with a machine
learning model, and has a Ryu controller install OpenFlow drop rules for the
sources it flags.

## Architecture

```
                         host1                                    host2
  ┌──────────────────────────────────────────────┐   ┌───────────────────────────┐
  │                                              │   │                           │
  │   sw1 ── dns        (10.0.1.0/24)  top       │   │   sw5 ── kafka   10.0.5.2 │
  │    │  └─ dns_collector                       │   │    │  ├─ kafdrop 10.0.5.6 │
  │   sw2 ── proxy      (10.0.2.0/24)  inter     │   │    │  ├─ minio   10.0.5.9 │
  │    │  └─ proxy_collector                     │   │    │  ├─ worker1  top     │
  │   sw3 ── webserver  (10.0.3.0/24)  bottom    │   │    │  ├─ worker2  inter   │
  │    │  └─ web_collector                       │   │    │  └─ worker3  bottom  │
  │   sw4 ── all collectors (10.0.4.0/24)        │   │                           │
  │                                              │   │                           │
  │   ryu  (host network, 6633 + 8080)           │   │                           │
  └───────────────────┬──────────────────────────┘   └─────────────┬─────────────┘
                      │            br0 ── GRE ── br0               │
                      └────────────────────────────────────────────┘
```

Each switch is an Open vSwitch instance in its own container, doing both L2
switching under controller control and L3 routing between the layer subnets.
Containers are attached with manually created veth pairs — Docker networking is
deliberately unused, so interface placement stays under the topology scripts'
control.

## How detection works

1. A collector mirrors its layer's service port and runs `tcpdump` for a
   30-second window.
2. The pcap is uploaded to MinIO; a Kafka message carries only a reference to
   it, since Kafka messages are capped at 1 MB.
3. The layer's worker consumes that reference, fetches the object, converts it
   to flow records with CICFlowMeter, and scores every flow.
4. Sources with at least `ALERT_MIN_FLOWS` flows scoring at or above
   `ALERT_THRESHOLD` are published to the `ddos-alerts` topic.
5. The Ryu controller consumes the alert and installs a drop rule matching that
   source IP on the switch for that layer.

The controller also carries the learning-switch logic. The bridges run
`fail-mode=secure`, so without it nothing forwards at all.

## Detection models

One detector per layer, each chosen independently. The layer decides *where* a
block is enforced; it says nothing about *which* algorithm scores it.

| Layer | Switch | Model directory | Currently |
|-------|--------|-----------------|-----------|
| top | br-sw1 | `build/worker/models/top` | XGBoost classifier |
| inter | br-sw2 | `build/worker/models/inter` | **rule-based placeholder** |
| bottom | br-sw3 | `build/worker/models/bottom` | **rule-based placeholder** |

XGBoost is simply what the top layer ships with today, not a requirement. Any
fitted estimator that exposes `predict_proba`, `decision_function` or `predict`
works — random forests, decision trees, logistic regression, k-NN, SVMs,
multi-layer perceptrons, gradient boosting, or a Keras/PyTorch model wrapped to
offer one of those methods. Different layers can use different algorithms, and
switching one is a file swap, not a code change. Each worker logs the algorithm
it loaded at startup, and the class name reaches the alert as, for example,
`top-randomforestclassifier`.

The intermediate and bottom layers currently run `HeuristicDetector`, a weighted
combination of flow statistics — SYN ratio, packet rate and packet size for the
intermediate layer; flow duration, byte starvation and request bursts for the
bottom layer. **These are placeholders, not trained models, and their scores
must not be read as model output.** Every worker says which it is using at
startup.

### Adding or replacing a model

Put the artifacts in the layer's model directory and restart that worker.

**A bare estimator** plus its preprocessing vectors, where the worker imputes,
orders and scales on the model's behalf:

```
build/worker/models/<layer>/
  models.joblib        the fitted estimator
  top_features.npy     feature names, in training order
  medians25.npy        per-feature median, for imputation
  scaler_mean25.npy    per-feature mean
  scaler_std25.npy     per-feature standard deviation
```

The vectors do not have to describe 25 features; the worker takes the count from
`top_features.npy` and refuses to start if the four files disagree. The order in
that file is authoritative — nothing in the code carries a feature list.

**A self-contained pipeline** that preprocesses internally — just
`models.joblib`. Anything with a `fit`/`predict` interface qualifies, including
an sklearn or imbalanced-learn `Pipeline` carrying its own imputer, scaler,
feature selection and sampler. It receives the flow records as a DataFrame,
reindexed to the columns its `feature_names_in_` declares, with absent ones left
for its own imputer.

The worker picks the mode automatically from which files it finds, and
`DETECTOR=model` forces it to refuse the heuristic fallback if the artifacts are
missing.

## Requirements

Two Ubuntu hosts with Docker, Docker Compose v2, Open vSwitch and Python 3 —
`utils/dependencies.sh` installs them.

## Addressing

Every address in the testbed is declared once, in
`startup/files/input/*.csv`, and nothing else hardcodes one.

| File | Holds |
|------|-------|
| `hosts.csv` | the two hosts' own addresses and management addresses |
| `switches.csv` | each switch's subnet, gateway and management address |
| `containers.csv` | every container's address on each switch |

`startup/scripts/update_env.py` renders those into `.env`, which the compose
files, the topology scripts and the containers all read. To move the testbed to
different machines, edit `hosts.csv` and redeploy — the GRE tunnel endpoints,
the bridge addresses and the container environments all follow.

`startup/scripts/generate_markdown.py` regenerates `ipmap.md` from the same
CSVs, so the documented inventory cannot drift from the deployed one.

## Bring-up

Host2 first, so Kafka and the workers exist before host1 starts publishing.

```bash
# on host2
sudo DDOS_DETECTION_HOME=$PWD ./deploy/host2.sh

# on host1
sudo DDOS_DETECTION_HOME=$PWD ./deploy/host1.sh
```

Both are idempotent. Pass `--clean` to tear down containers and OVS state first.
Each script generates `.env` from the CSV inventory, builds and starts the
containers, runs the numbered topology scripts in order, and prints a health
check.

The numbered scripts in `host1/` and `host2/` still run standalone if you prefer
to step through the topology by hand.

## Verifying

```bash
# the data plane forwards
docker exec proxy ping -c3 10.0.1.2
docker exec proxy dig @10.0.1.2 cyberstuff.local +short
docker exec dns_collector ping -c3 10.0.5.2        # across the GRE tunnel

# the controller sees every switch
curl -s http://127.0.0.1:8080/ddos/status

# captures are flowing
docker exec kafka kafka-topics --bootstrap-server 10.0.5.2:9092 --list
docker logs --tail 20 worker1                       # on host2
```

## Attacks

```bash
./attacks/install-tools.sh          # hping3, dnsperf, slowhttptest, ab, scapy
DURATION=300 ./attacks/top.sh       # DNS amplification, flood, reflection
DURATION=300 ./attacks/inter.sh     # SYN and UDP floods at the proxy
DURATION=300 ./attacks/bottom.sh    # slow headers and a request burst
./attacks/watch.sh                  # live view of alerts, blocks and flow rules
```

Each defaults to a ten-minute run and takes `TARGET` to point elsewhere.

The host's own address and the protected services are whitelisted, so a flood
launched from the host is detected but deliberately not blocked. To see a rule
installed, give the flood a source that is not whitelisted:

```bash
SPOOF_SOURCE=10.0.1.50 DURATION=180 ./attacks/top.sh
```

After an attack, a blocked source appears in three places:

```bash
curl -s http://127.0.0.1:8080/ddos/blocks
docker exec sw1 ovs-ofctl -O OpenFlow13 dump-flows br-sw1 | grep priority=100
docker logs ryu | grep BLOCK
```

## Mitigation API

Served on port 8080 beside `ryu.app.ofctl_rest`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ddos/status` | connected datapaths, alert and block counts |
| GET | `/ddos/blocks` | active blocks with remaining TTL |
| POST | `/ddos/blocks` | install a block by hand |
| DELETE | `/ddos/blocks/{ip}` | clear a block |

## Configuration

All of it reaches the containers through the generated `.env`.

| Variable | Default | Meaning |
|----------|---------|---------|
| `CAPTURE_DURATION` | `30` | capture window, seconds |
| `CAPTURE_INTERFACE` | `eth0` | interface each collector listens on |
| `ALERT_THRESHOLD` | `0.5` | probability at or above which a flow counts as malicious |
| `ALERT_MIN_FLOWS` | `10` | malicious flows from one source before an alert; `1` alerts on any single flow |
| `MAX_LAG_SECONDS` | `120` | skip captures older than this; `0` disables the check |
| `BLOCK_HARD_TIMEOUT` | `300` | drop-rule lifetime, seconds; `0` never expires |
| `BLOCK_PRIORITY` | `100` | OpenFlow priority of drop rules |
| `BLOCK_WHITELIST` | gateways, collectors, mgmt range, host2 services | never blocked |
| `LAYER_DATAPATH_MAP` | `top:1,inter:2,bottom:3` | which switch enforces which layer |
| `WORKER_JAVA_OPTS` | `-Xms256m -Xmx1g` | CICFlowMeter heap |

The whitelist matters: an alert naming a gateway or a collector would partition
the testbed, so those addresses are refused and logged.

## Flow features

Captures become flow records with CICFlowMeter-4.0, vendored under
`build/worker/cicflowmeter` (an 11MB subset of the distribution: the GUI and
machine-learning jars are not needed by the command-line entry point). The
upstream project keeps it in a git submodule that its source archive does not
carry, so it is committed here to keep the image reproducible and buildable
offline.

The converter's column names differ from the CIC-DDoS2019 names the models were
trained on — `Total Bwd packets` against `Total Backward Packets`, and so on —
so `features.py` renames them. `tests/test_feature_coverage.py` holds a fixture
of real converter output and asserts every feature the model expects resolves
from it; without that check a name change would be absorbed silently as an
imputed median and the probabilities would mean nothing.

## Tests

```bash
python3 -m pytest
```

Unit tests only — no network, no Docker. They cover the feature pipeline and its
ordering, the detectors, alert aggregation, the CICFlowMeter wrapper, the
whitelist, the block table and flow construction, and the compose manifests.

## Layout

```
attacks/       the three attack scenarios and a live monitor
build/         one directory per image
  collector/   packet capture, one image parameterised by layer
  worker/      the detection pipeline, the models and the flow converter
  ryu-controller/  the learning switch and DDoS blocker
deploy/        per-host bring-up
host1/ host2/  numbered topology scripts
startup/       CSV inventory, env template, generators
tests/         pytest suite
tools/         offline helpers
utils/         dependencies, cleanup
```
