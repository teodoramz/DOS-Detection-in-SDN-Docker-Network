# What the shipped models do on testbed traffic

Measured 2026-10-24 on the two-host testbed, with the artifacts committed under
`build/worker/models/`. The flows are the committed gate sets
(`training/data/testbed_<layer>.csv.gz`), scored through the worker's own
`ModelDetector`, inside the worker container that serves that layer.

## How the sets were collected

| Class | Traffic |
|-------|---------|
| benign (`y=0`) | `dig` against the resolver, `curl` to the web server directly and through the proxy, ICMP — roughly three requests a second for 100 s |
| attack (`y=1`) | the layer's own scenario from `attacks/`, with `SPOOF_SOURCE=10.255.255.200` |

Three consecutive 30-second windows per class, converted by the vendored
CICFlowMeter-4.0, capped at 20,000 rows per class.

The spoofed source matters twice over. It is unreachable, so nothing answers it
and the flows stay unidirectional — the shape a real spoofed flood has. And it
sits inside the whitelisted management range, so no drop rule lands partway
through and cuts off the very traffic being captured.

## Per-flow scores

| Layer | Attack flows | median p | ≥ 0.5 | Benign flows | median p | ≥ 0.5 |
|-------|--------------|----------|-------|--------------|----------|-------|
| top | 545 | 0.9996 | 545 (100%) | 185 | 1.0000 | 185 (100%) |
| inter | 51 | 0.5573 | 48 (94%) | 210 | 0.0113 | 0 |
| bottom | 15,486 | 0.1908 | 118 (0.8%) | 441 | 0.1856 | 0 |

## Under the deployed alert rule

At least `ALERT_MIN_FLOWS` (10) flows from one source at or above
`ALERT_THRESHOLD` (0.5).

| Layer | Sources that would alert | Which |
|-------|--------------------------|-------|
| top | 2 | the attacker, and the resolver itself |
| inter | 1 | the attacker only — 48 of 48 flows |
| bottom | 3 | the attacker (48 of 48 spoofed flows), the host, and the web server |

## Reading this

- **inter** separates cleanly: 0.0113 on benign against 0.5573 on attack flows,
  and the only source it alerts on is the attacker. The margin over the 0.5
  threshold is thin, so a retrained model should widen it, but the model works.
- **bottom** keeps benign below 0.43 while the spoofed attacker scores above the
  threshold on all 48 of its flows. It also names the web server, whose address
  is whitelisted, so that costs nothing here.
- **top** fires on the attack and on everything else: benign DNS lookups score
  1.0000 as well. It separates nothing. It looks correct in a demonstration only
  because every legitimate address in the testbed is whitelisted, so the
  attacker is the only source that can produce a block.

## What changed this picture

An earlier run of the same measurement had inter at 0.0002 on attack flows and
bottom alerting only on the victim. The models had not changed — the attack had.
`hping3 --flood` walks the whole source port space, so each 5-tuple carried one
or two packets at a fraction of a packet per second, and CICFlowMeter discards
single-packet flows outright. What reached the detector was not a flood.
`launch_spoofed_flows` now holds 16 source ports open with 512-byte payloads at
hping3's own rate, which is both a more honest attack and traffic the models
recognise. The lesson is in the method, not the models: a detector can only be
judged on traffic that resembles what it will meet.
