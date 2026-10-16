#!/usr/bin/env bash
# SRT3 security collector - writes Prometheus metrics for node_exporter's textfile collector.
# Runs every minute via srt3-security.timer. Read-only: it only inspects, never changes anything.
set -u
DIR=/var/lib/prometheus/node-exporter; OUT=$DIR/srt3_security.prom; TMP=$(mktemp "$DIR/.srt3_security.XXXX")
{
echo '# HELP srt3_listening_port Listening TCP/UDP socket (addr="any" = reachable from network, "local" = loopback only).'
echo '# TYPE srt3_listening_port gauge'
ss -Hltunp 2>/dev/null | awk '{
  proto=$1; local=$5; proc=$0; sub(/.*users:\(\("/,"",proc); sub(/".*/,"",proc); if (proc==$0) proc="unknown";
  n=split(local,a,":"); port=a[n]; addr=substr(local,1,length(local)-length(port)-1);
  scope=(addr ~ /^(127\.|\[::1\]|::1|\[::ffff:127\.)/) ? "local" : "any";
  if (proto=="udp" && port+0>=32768) next;   # skip ephemeral UDP client sockets
  key=proto" "port" "scope" "proc; if (!(key in seen)) { seen[key]=1;
    printf "srt3_listening_port{proto=\"%s\",port=\"%s\",addr=\"%s\",process=\"%s\"} 1\n", proto, port, scope, proc } }'

PA=$(sshd -T 2>/dev/null | awk '/^passwordauthentication /{print $2}')
PR=$(sshd -T 2>/dev/null | awk '/^permitrootlogin /{print $2}')
echo '# HELP srt3_ssh_password_auth 1 if sshd accepts password logins.'
echo '# TYPE srt3_ssh_password_auth gauge'
echo "srt3_ssh_password_auth $([ "$PA" = yes ] && echo 1 || echo 0)"
echo '# HELP srt3_ssh_permit_root_login sshd PermitRootLogin mode (value always 1).'
echo '# TYPE srt3_ssh_permit_root_login gauge'
echo "srt3_ssh_permit_root_login{mode=\"${PR:-unknown}\"} 1"

SSHF=$(journalctl --since -15min -q --no-pager -u ssh -u sshd 2>/dev/null | grep -cE 'Failed password|Invalid user|authentication failure|Connection closed by authenticating user')
PVEF=$(journalctl --since -15min -q --no-pager -u pvedaemon -u pveproxy 2>/dev/null | grep -c 'authentication failure')
echo '# HELP srt3_auth_failures_15m Failed login attempts in the last 15 minutes.'
echo '# TYPE srt3_auth_failures_15m gauge'
echo "srt3_auth_failures_15m{service=\"ssh\"} $SSHF"
echo "srt3_auth_failures_15m{service=\"proxmox\"} $PVEF"
echo '# HELP srt3_logged_in_sessions Interactive login sessions right now.'
echo '# TYPE srt3_logged_in_sessions gauge'
echo "srt3_logged_in_sessions $(who | wc -l)"
echo '# HELP srt3_security_last_run_timestamp_seconds When this collector last ran.'
echo '# TYPE srt3_security_last_run_timestamp_seconds gauge'
echo "srt3_security_last_run_timestamp_seconds $(date +%s)"
} > "$TMP" && chmod 644 "$TMP" && mv "$TMP" "$OUT"
