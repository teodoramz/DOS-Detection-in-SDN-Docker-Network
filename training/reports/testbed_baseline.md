# What the detectors do on testbed traffic

Measured 2026-10-25 on the two-host testbed with the artifacts committed under
`build/worker/models/`. The flows are the committed gate sets
(`training/data/testbed_<layer>.csv.gz`), scored through the worker's own
`ModelDetector` and `HeuristicDetector`, inside the worker container that serves
that layer.

## How the sets were collected

| Class | Traffic |
|-------|---------|
| benign (`y=0`) | one DNS lookup every three seconds from the proxy container, varied names, plus HTTP requests to the web server directly and through the proxy — ten 30-second windows |
| attack (`y=1`) | the layer's own scenario from `attacks/`, with `SPOOF_SOURCE=10.255.255.200` — three windows |

The benign class is generated deliberately and at a low rate from *inside* the
topology. An idle testbed yields one or two flows a window, which cannot detect
a false positive, and benign traffic hosed out at three requests a second is
itself flood-shaped — an earlier version of this measurement made that mistake
and produced a misleading table.

The spoofed attack source matters twice over. It is unreachable, so nothing
answers it and the flows stay unidirectional, which is the shape a real spoofed
flood has. And it sits inside the whitelisted management range, so no drop rule
lands partway through and cuts off the traffic being captured.

## The trained models

| Layer | Attack flows ≥ 0.5 | median | Benign flows ≥ 0.5 | median | Benign sources alerted |
|-------|--------------------|--------|--------------------|--------|------------------------|
| top | 545 / 545 | 0.9996 | **96 / 96** | 1.0000 | **1 of 2** |
| inter | 48 / 51 | 0.5573 | 0 / 352 | 0.0007 | 0 of 3 |
| bottom | 118 / 15,486 | 0.1908 | 0 / 158 | 0.2938 | 0 of 1 |

## Model against placeholder, same data, same rule

At least `ALERT_MIN_FLOWS` (10) flows from one source at or above
`ALERT_THRESHOLD` (0.5).

| Layer | Detector | Attack flows over | Benign flows over | Benign sources alerted |
|-------|----------|-------------------|-------------------|------------------------|
| inter | model | 48 / 51 | 0 / 352 | 0 of 3 |
| inter | heuristic | 48 / 51 | **259 / 352** | **3 of 3** |
| bottom | model | 118 / 15,486 | 0 / 158 | 0 of 1 |
| bottom | heuristic | 441 / 15,486 | 0 / 158 | 0 of 1 |

`HeuristicDetector` exists only for the intermediate and bottom layers; the top
layer has no placeholder to fall back to.

## Reading this

- **inter**: the model is the right detector. It separates cleanly — 0.0007 on
  benign against 0.5573 on attack — and alerts on the attacker alone. The
  placeholder reaches the same attack flows but also crosses the threshold on
  259 benign flows and would alert on *every* legitimate source in the set. Only
  the whitelist stops that becoming three wrongly blocked clients. The model's
  margin over the threshold is thin, which is what retraining should widen.
- **bottom**: both detectors are clean on benign traffic. The model alerts on
  the spoofed attacker; the placeholder flags more attack flows but one fewer
  source. The model is the better documented of the two.
- **top**: the weak one. Every benign flow scores at or above 0.9987, so the
  model alerts on `10.0.2.2` — a legitimate client doing 87 DNS lookups over
  five minutes. It fires on attacks, and on everything else. It looks correct in
  a demonstration only because every legitimate address in this topology is
  whitelisted, so the attacker is the only source that can produce a block. In a
  network where clients were not whitelisted, this layer would block them.
  Retraining the top model on local traffic is the single highest-value change
  left in the project.

## What changed this picture

An earlier run of this measurement had inter at 0.0002 on attack flows and
bottom alerting only on the victim. The models had not changed — the attack had.
`hping3 --flood` walks the whole source port space, so each 5-tuple carried one
or two packets at a fraction of a packet per second, and CICFlowMeter discards
single-packet flows outright. What reached the detector was not a flood.
`launch_spoofed_flows` now holds 16 source ports open with 512-byte payloads at
hping3's own rate, which is both a more honest attack and traffic the models
recognise. A detector can only be judged on traffic that resembles what it will
meet.
