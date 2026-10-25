#!/bin/bash
# Bring the whole testbed up on two fresh machines from one command.
#
#   ./deploy/remote.sh --host1 teoos@192.168.1.10 --host2 teoos@192.168.1.11
#
# Credentials come from the environment or a prompt, never from the command
# line, because arguments are visible to every user on the machine:
#
#   DDOS_SSH_PASSWORD   ssh and scp password; omit it to use ssh keys
#   DDOS_SUDO_PASSWORD  sudo password on the hosts; defaults to the ssh one
#
# Re-runnable. The hosts keep their data and containers unless --clean is given.

set -euo pipefail

source "$(dirname "$0")/lib.sh"

HOST1=""
HOST2=""
REMOTE_DIR="ddos"
CLEAN=""
SKIP_DEPS=""
ASK=""

usage() {
  cat <<USAGE
Usage: $0 --host1 user@address --host2 user@address [options]

  --host1 user@address   the machine that runs the three layers and Ryu
  --host2 user@address   the machine that runs Kafka, MinIO and the workers
  --dir NAME             directory to deploy into, under the remote home
                         (default: ${REMOTE_DIR})
  --clean                tear down containers and OVS state first
  --skip-deps            do not install packages on the hosts
  --ask                  prompt for the password instead of reading the
                         DDOS_SSH_PASSWORD environment variable
  --help                 this text

Credentials: set DDOS_SSH_PASSWORD (and DDOS_SUDO_PASSWORD if it differs), or
use --ask, or leave both unset to authenticate with ssh keys.

Host2 is brought up first: host1 starts publishing captures as soon as its
collectors run, so the broker and the workers have to be listening already.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --host1) HOST1="${2:-}"; shift 2 ;;
    --host2) HOST2="${2:-}"; shift 2 ;;
    --dir) REMOTE_DIR="${2:-}"; shift 2 ;;
    --clean) CLEAN="--clean"; shift ;;
    --skip-deps) SKIP_DEPS=1; shift ;;
    --ask) ASK=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done

[ -n "$HOST1" ] || { usage >&2; die "--host1 is required"; }
[ -n "$HOST2" ] || { usage >&2; die "--host2 is required"; }

if [ -n "$ASK" ]; then
  read -rsp "ssh password: " DDOS_SSH_PASSWORD; echo
fi

SSH_PASSWORD="${DDOS_SSH_PASSWORD:-}"
SUDO_PASSWORD="${DDOS_SUDO_PASSWORD:-$SSH_PASSWORD}"

SSH_OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
          -o LogLevel=ERROR -o ConnectTimeout=15)

if [ -n "$SSH_PASSWORD" ]; then
  command -v sshpass >/dev/null || die "sshpass is needed for password login; install it or use ssh keys"
  export SSHPASS="$SSH_PASSWORD"
  SSH=(sshpass -e ssh "${SSH_OPTS[@]}")
  SCP=(sshpass -e scp "${SSH_OPTS[@]}")
else
  SSH=(ssh "${SSH_OPTS[@]}")
  SCP=(scp "${SSH_OPTS[@]}")
fi

address_of() { echo "${1##*@}"; }
HOST1_IP=$(address_of "$HOST1")
HOST2_IP=$(address_of "$HOST2")

on() {
  local target=$1; shift
  "${SSH[@]}" "$target" "$@"
}

# Runs a command under sudo on a host, feeding the password on stdin so it
# never appears in the process list or the shell history.
sudo_on() {
  local target=$1; shift
  if [ -n "$SUDO_PASSWORD" ]; then
    "${SSH[@]}" "$target" "sudo -S -p '' $*" <<< "$SUDO_PASSWORD"
  else
    "${SSH[@]}" "$target" "sudo -n $*"
  fi
}

say "Checking both hosts are reachable"
for target in "$HOST1" "$HOST2"; do
  on "$target" true || die "cannot reach $target over ssh"
  printf '  %s ok\n' "$target"
done

say "Writing the host inventory"
render_hosts_csv "$HOST1_IP" "$HOST2_IP" startup/files/input/hosts.csv
printf '  host1 %s, host2 %s\n' "$HOST1_IP" "$HOST2_IP"

say "Copying the project to both hosts"
BUNDLE=$(mktemp /tmp/ddos-bundle-XXXXXX.tar.gz)
trap 'rm -f "$BUNDLE"' EXIT
tar czf "$BUNDLE" \
  --exclude=.git --exclude=volumes --exclude=__pycache__ --exclude=.pytest_cache \
  --exclude='*.pcap' --exclude='*.pdf' --exclude='*.zip' .
for target in "$HOST1" "$HOST2"; do
  on "$target" "rm -rf ~/${REMOTE_DIR}.incoming && mkdir -p ~/${REMOTE_DIR}.incoming"
  "${SCP[@]}" "$BUNDLE" "$target:~/${REMOTE_DIR}.incoming/bundle.tar.gz"
  on "$target" "tar xzf ~/${REMOTE_DIR}.incoming/bundle.tar.gz -C ~/${REMOTE_DIR}.incoming \
                && mkdir -p ~/${REMOTE_DIR} \
                && cp -a ~/${REMOTE_DIR}.incoming/. ~/${REMOTE_DIR}/ \
                && rm -rf ~/${REMOTE_DIR}.incoming \
                && chmod +x ~/${REMOTE_DIR}/deploy/*.sh ~/${REMOTE_DIR}/host*/*.sh \
                           ~/${REMOTE_DIR}/utils/*.sh ~/${REMOTE_DIR}/attacks/*.sh"
  printf '  %s:~/%s\n' "$target" "$REMOTE_DIR"
done

if [ -z "$SKIP_DEPS" ]; then
  say "Installing packages"
  for target in "$HOST1" "$HOST2"; do
    printf '  %s\n' "$target"
    sudo_on "$target" "apt-get update -qq" >/dev/null 2>&1 || warn "apt-get update failed on $target"
    sudo_on "$target" "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        curl openvswitch-switch iproute2 docker.io docker-compose-v2 \
        python3-pandas python3-jinja2 sshpass" >/dev/null 2>&1 \
      || warn "some packages did not install on $target; see utils/dependencies.sh"
  done
fi

say "Bringing up host2 (broker, object store, workers)"
sudo_on "$HOST2" "env DDOS_DETECTION_HOME=\$HOME/${REMOTE_DIR} \
    \$HOME/${REMOTE_DIR}/deploy/host2.sh ${CLEAN}" || die "host2 deployment failed"

say "Bringing up host1 (three layers, collectors, Ryu)"
sudo_on "$HOST1" "env DDOS_DETECTION_HOME=\$HOME/${REMOTE_DIR} \
    \$HOME/${REMOTE_DIR}/deploy/host1.sh ${CLEAN}" || die "host1 deployment failed"

say "Verifying"
printf '  controller: '
on "$HOST1" "curl -s --max-time 10 http://127.0.0.1:8080/ddos/status" || warn "no answer from the controller"
printf '\n'
for pair in "$HOST1:11" "$HOST2:7"; do
  target=${pair%:*}; expected=${pair##*:}
  running=$(sudo_on "$target" "docker ps -q" | wc -l | tr -d ' ')
  printf '  %s: %s of %s containers running\n' "$(address_of "$target")" "$running" "$expected"
done

say "Testbed is up"
cat <<NEXT
  controller API   http://${HOST1_IP}:8080/ddos/status
  kafka console    http://${HOST2_IP}:9000   (kafdrop)
  attack it with   ssh ${HOST1} 'cd ~/${REMOTE_DIR} && sudo SPOOF_SOURCE=10.0.2.55 ./attacks/inter.sh'
NEXT
