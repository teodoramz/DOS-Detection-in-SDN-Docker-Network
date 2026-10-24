# What the shipped models do on testbed traffic

Measured 2026-10-24 on the two-host testbed, with the artifacts committed under
`build/worker/models/`. The flows are the committed gate sets
(`training/data/testbed_<layer>.csv.gz`), scored through the worker's own
`ModelDetector`, inside the worker container that serves that layer.

## How the sets were collected

| Class | Traffic |
|-------|---------|
| benign (`y=0`) | `dig` against the resolver, `curl` to the web server directly and through the proxy, ICMP — roughly three requests a second for 100 s |
| attack (`y=1`) | the layer's own scenario from `attacks/`, run **without** `SPOOF_SOURCE` so the source stays whitelisted and no drop rule cuts the capture short |

Three consecutive 30-second windows per class, converted by the vendored
CICFlowMeter-4.0, capped at 20,000 rows per class.

## Per-flow scores

| Layer | Attack flows | median p | ≥ 0.5 | Benign flows | median p | ≥ 0.5 |
|-------|--------------|----------|-------|--------------|----------|-------|
| top | 490 | 0.9996 | 490 (100%) | 47 | 1.0000 | 47 (100%) |
| inter | 20,000 | 0.0002 | 0 | 212 | 0.0113 | 0 |
| bottom | 20,000 | 0.1908 | 230 (1.2%) | 407 | 0.1856 | 0 |

## Under the deployed alert rule

At least `ALERT_MIN_FLOWS` (10) flows from one source at or above
`ALERT_THRESHOLD` (0.5).

| Layer | Sources that would alert | Which |
|-------|--------------------------|-------|
| top | 1 | the attacker (302 of 302 flows malicious) |
| inter | 0 | — |
| bottom | 1 | `10.0.3.2`, the web server being attacked, not the attacker |

## Reading this

- **top** fires on the attack, and on everything else: benign DNS lookups score
  1.0000 as well. It separates nothing. It looks correct in a demonstration only
  because every legitimate address in the testbed is whitelisted, so the
  attacker is the only source that can produce a block.
- **inter** never crosses the threshold. Earlier live checks pinned its output at
  0.325 across 0.1 → 1,678 packets/s, 50,000-packet flows and 512-byte payloads,
  so this is not a question of the attack being too weak.
- **bottom** is the only one with usable separation — benign stays below 0.43
  while 230 attack flows reach 0.9988 — but it attributes the attack to the
  victim's side of the flow, and that address is whitelisted, so the attacker
  goes free.

Hence `WORKER_INTER_DETECTOR` and `WORKER_BOTTOM_DETECTOR` run the heuristic:
the placeholders block the attacker, these models do not. The numbers above are
the baseline a retrained model has to beat, and section 8 of
`train_layer_model.ipynb` recomputes exactly this table.
