#!/bin/bash
# SRT3 10G benchmark: Viper <-> Demon over 10.10.10.x (iperf3, 4 streams, 45 s per phase).
# Results go to node_exporter's textfile collector on Viper -> Prometheus (srt3_iperf_*),
# shown in Grafana -> SRT3 Network -> 10G fabric. Run on Viper:
#   systemd-run --unit=srt3-iperf --collect /root/srt3-iperf.sh
D=192.168.8.230; DIR=/var/lib/prometheus/node-exporter
export DEBIAN_FRONTEND=noninteractive
command -v iperf3 >/dev/null || apt-get install -y iperf3
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new root@$D 'command -v iperf3 >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get install -y iperf3; pkill -x iperf3; iperf3 -s -D' || exit 1
sleep 2
for t in push pull bidir; do
  case $t in push) f=;; pull) f=-R;; bidir) f=--bidir;; esac
  iperf3 -c 10.10.10.230 -t 45 -P 4 $f -J > /tmp/iperf-$t.json; sleep 10
done
ssh root@$D pkill -x iperf3
python3 - > $DIR/srt3_iperf.prom.tmp <<'PY'
import json,time
for t in ("push","pull","bidir"):
    e=json.load(open(f"/tmp/iperf-{t}.json"))["end"]
    bps=e["sum_received"]["bits_per_second"]+e.get("sum_received_bidir_reverse",{}).get("bits_per_second",0)
    rt=e["sum_sent"].get("retransmits",0)+e.get("sum_sent_bidir_reverse",{}).get("retransmits",0)
    print(f'srt3_iperf_gbps{{test="{t}"}} {bps/1e9:.3f}')
    print(f'srt3_iperf_retransmits{{test="{t}"}} {rt}')
print(f"srt3_iperf_last_run_timestamp_seconds {time.time():.0f}")
PY
mv $DIR/srt3_iperf.prom.tmp $DIR/srt3_iperf.prom
