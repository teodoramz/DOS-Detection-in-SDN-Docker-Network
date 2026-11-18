# Dependency audit

Audited offline with `pip-audit` (PyPI advisories) and the OSV API (Maven). Dependabot's alert list was not readable, so the count GitHub shows (22) could not be matched one-to-one; this table is what the manifests and vendored jars actually contain.

## Python

| Component | Was | Advisories | Fixed in | Action |
|---|---|---|---|---|
| kafka-python (worker, collector, ryu) | 2.2.15 / 2.0.2 | CVE-2026-10142, CVE-2026-10143 (high) | 2.3.2 | bumped to 2.3.2 |
| Flask (webserver) | 3.0.3 | PYSEC-2026-2151 | 3.1.3 | bumped to 3.1.3 |
| python-dotenv (webserver) | 1.0.1 | PYSEC-2026-2270 | 1.2.2 | bumped to 1.2.2 |
| webob (ryu) | 1.8.7 | CVE-2024-42353, CVE-2026-44889, CVE-2026-54770 (moderate) | 1.8.11 | bumped to 1.8.11 |
| eventlet (ryu) | 0.30.2 | CVE-2021-21419, CVE-2023-29483, CVE-2025-58068 | 0.31 to 0.40.3 | accepted |
| dnspython (ryu) | 1.16.0 | CVE-2023-29483, CVE-2026-114605, CVE-2026-128089 (high) | 2.6.1 to 2.9.2 | accepted |
| ryu | 4.34 | CVE-2020-35139, CVE-2020-35141, CVE-2024-28732, CVE-2024-34483/84/86/87/88/89 | none (unmaintained) | accepted |
| pandas, numpy, scikit-learn, imbalanced-learn, xgboost, joblib, minio, jinja2 | as pinned | none | | unchanged |

Accepted items: ryu 4.34 requires eventlet<0.31, which requires dnspython<2; moving any of them breaks the controller (see `.github/dependabot.yml`). The controller is only reachable from the internal OpenFlow and management networks.

scikit-learn stays 1.6.1 and xgboost 2.1.3 because the committed pickles were trained on them; `models/{top,inter,bottom}/models.joblib` load under the pinned set after the bumps above.

## Vendored CICFlowMeter jars (`build/worker/cicflowmeter/lib`)

The worker runs `cic.cs.unb.ca.ifm.Cmd` on local pcaps through `flowmeter.pcap_to_csv`. Loaded jars were listed with `-verbose:class`: CICFlowMeter, jnetpcap, commons-io, commons-math3, tika-core, slf4j-api, slf4j-log4j12 and log4j 1.2.17. log4j-core/api 2.x, guava and commons-lang3 are never loaded, and CICFlowMeter-4.0.jar contains no reference to `org.apache.logging`; its logging goes through slf4j-log4j12 to log4j 1.x. guava is referenced only from the Swing UI and the Weka code.

| Component | Was | Advisories | Fixed in | Action |
|---|---|---|---|---|
| log4j-core / log4j-api | 2.11.0 | CVE-2021-44228, CVE-2021-45046 (critical), CVE-2021-45105, CVE-2021-44832, CVE-2020-9488, 2026 moderates | 2.25.4 | removed; not referenced by any loaded class |
| log4j | 1.2.17 | CVE-2019-17571, CVE-2022-23302/05/07, CVE-2021-4104, CVE-2023-26464 | none | replaced by reload4j 1.2.25 (drop-in, same `org.apache.log4j` API); no open advisories |
| guava + annotation companions | 23.6-jre | CVE-2018-10237, CVE-2020-8908, CVE-2023-2976, CVE-2026-102554 | 33.x | removed (UI-only, unreachable headless) |
| commons-io | 2.5 | CVE-2024-47554 (high), CVE-2021-29425 | 2.14 | 2.18.0 |
| commons-lang3 | 3.6 | CVE-2025-48924 | 3.18.0 | 3.18.0 |
| tika-core | 1.17 | CVE-2018-11761, CVE-2019-10088, CVE-2019-10094 and others | 1.28.3 | 1.28.5 |
| tika-core | 1.28.5 | CVE-2025-66516 (PDF/XFA XXE) | 3.2.2 (major API change) | accepted: only MIME detection is used, no PDF parsing |
| commons-math3, slf4j 1.7.25, java-cup, jnetpcap | | none known | | unchanged |

Replacement jars come from Maven Central and their SHA-1 matched the published `.sha1`. `-Dlog4j2.formatMsgNoLookups=true` stays in `JAVA_OPTS` as a harmless guard.

Verification: a synthetic pcap (5 TCP sessions and 4 UDP packets, generated with scapy) was converted through `pcap_to_csv` before and after the jar changes. The CSVs are byte-identical and the converter's file logging still works through reload4j.

## Base images (not changed)

| Image | Note |
|---|---|
| `ubuntu:20.04` (openvswitch, ubuntu-net) | EOL; kept because the switch image and lab tools target it. Moving it needs a re-test of the switch image. |
| `python:3.9-slim` (ryu) | 3.9 is EOL; held back by ryu 4.34 needing old setuptools and eventlet. |
| `python:3.12-slim` (worker, collector, webserver) | supported. |
| `confluentinc/cp-kafka:7.8.0`, `obsidiandynamics/kafdrop:4.1.0` | not the latest; no patch-level tag was verified, so unchanged. |
| `chainguard/minio:latest`, `nginx:alpine` | floating tags; pick up upstream fixes on rebuild but are not reproducible. |
| `internetsystemsconsortium/bind9:9.18` | supported ESV branch, floating patch. |

OS-package CVEs inside the built images (for example the JRE in the worker) were not scanned here; run `trivy image` on a built image to cover them.
