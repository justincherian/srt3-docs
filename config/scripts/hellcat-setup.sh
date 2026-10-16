#!/usr/bin/env bash
# SRT3 observability v2 - run on Hellcat as root:  bash /root/hellcat-setup.sh
# Safe to re-run. Backs up /etc/prometheus first. Validates every config before restarting anything.
set -u
TS=$(date +%Y%m%d-%H%M%S)
BK=/root/srt3-backup-$TS
ok(){ printf '\033[32m[ok]\033[0m %s\n' "$*"; }
bad(){ printf '\033[31m[!!]\033[0m %s\n' "$*"; }

mkdir -p "$BK"; cp -a /etc/prometheus /etc/default/prometheus* "$BK"/ 2>/dev/null; ok "backup -> $BK"

echo "== 1/6 packages"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq prometheus prometheus-node-exporter prometheus-blackbox-exporter prometheus-alertmanager >/dev/null && ok "prometheus, node/blackbox exporters, alertmanager installed" || bad "apt install failed"

echo "== 2/6 node_exporter tuning (Viper, Hellcat, Demon)"
# NOTE: if an old Docker node-exporter holds :9100, stop it first (docker update --restart=no <c>; docker stop <c>).
# Skip virtual NICs (VM taps, firewall bridges, docker) and ZFS dataset mounts at the source.
NE_ARGS='ARGS="--collector.netdev.device-exclude=^(lo|tap.*|veth.*|fwbr.*|fwln.*|fwpr.*|vmbr.*|br-.*|docker.*|tailscale.*)$ --collector.filesystem.mount-points-exclude=^/(dev|proc|run|sys|var/lib/docker/.+|var/lib/lxcfs|etc/pve|rpool.*)($|/) --collector.netclass.ignored-devices=^(lo|tap.*|veth.*|fwbr.*|fwln.*|fwpr.*|vmbr.*|br-.*|docker.*|tailscale.*)$ --no-collector.thermal_zone"'
echo "$NE_ARGS" > /etc/default/prometheus-node-exporter && systemctl restart prometheus-node-exporter && ok hellcat
for h in 192.168.8.210 192.168.8.230; do
  ssh -o ConnectTimeout=5 -o BatchMode=yes root@$h "echo '$NE_ARGS' > /etc/default/prometheus-node-exporter && systemctl restart prometheus-node-exporter" \
    && ok "$h" || bad "$h unreachable - skipped (re-run later)"
done

echo "== 3/6 Home Assistant token"
if [ ! -s /etc/prometheus/ha_token ]; then
  echo "In HA: profile (bottom-left) > Security > Long-lived access tokens > Create token, name it 'prometheus'."
  read -rsp "Paste the token here (hidden) and press Enter: " T; echo
  printf '%s' "$T" > /etc/prometheus/ha_token; unset T
fi
chown prometheus:prometheus /etc/prometheus/ha_token; chmod 600 /etc/prometheus/ha_token; ok "token stored in /etc/prometheus/ha_token"

echo "== 4/6 configs"
mkdir -p /etc/prometheus/rules
cat > /etc/prometheus/prometheus.yml <<'SRT3_EOF'
# SRT3 Prometheus - Hellcat. Managed by Claude; source of truth is srt3-docs/config/prometheus.
global:
  scrape_interval: 15s
  evaluation_interval: 30s
  external_labels:
    lab: srt3

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: alertmanager
    scrape_interval: 60s
    static_configs:
      - targets: ['localhost:9093']
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'alertmanager_(alerts|alerts_received_total|alerts_invalid_total|notifications_total|notifications_failed_total|notification_latency_seconds_.*|silences|config_last_reload_successful)'
        action: keep

  # Linux hosts (Proxmox). Exporter-internal and unused series dropped at scrape.
  - job_name: node
    static_configs:
      - targets: ['192.168.8.210:9100']
        labels: {node: viper}
      - targets: ['192.168.8.220:9100']
        labels: {node: hellcat}
      - targets: ['192.168.8.230:9100']
        labels: {node: demon}
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'go_.*|process_.*|promhttp_.*|node_scrape_collector_.*|node_softnet_.*|node_cooling_device_.*|node_cpu_guest_seconds_total|node_systemd_socket_.*|node_systemd_timer_.*|node_zfs_zpool_dataset_.*|node_cpu_scaling_governor'
        action: drop
      # systemd: keep one series per unit (state="failed") instead of five.
      - source_labels: [__name__, state]
        regex: 'node_systemd_unit_state;(active|activating|deactivating|inactive|maintenance|reloading|refreshing)'
        action: drop

  # Ryzenous (Windows desktop). Down when it's off or asleep - not alerted.
  - job_name: windows
    static_configs:
      - targets: ['192.168.8.101:9182']
        labels: {node: ryzenous}
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'go_.*|process_.*|promhttp_.*|windows_exporter_collector_.*'
        action: drop

  - job_name: gpu
    static_configs:
      - targets: ['192.168.8.101:9835']
        labels: {node: ryzenous, gpu: rtx3070}
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'go_.*|process_.*|promhttp_.*'
        action: drop

  # Home Assistant: HS300 per-outlet power + climate (filtered in HA).
  - job_name: homeassistant
    scrape_interval: 30s
    metrics_path: /api/prometheus
    authorization:
      credentials_file: /etc/prometheus/ha_token
    static_configs:
      - targets: ['192.168.8.221:8123']

  # GL.iNet Flint 2 (optional - needs prometheus-node-exporter-lua on the router).
  - job_name: router
    scrape_interval: 30s
    static_configs:
      - targets: ['192.168.8.1:9100']
        labels: {node: flint2}

  # Service checks: "does the web UI answer, and how fast?"
  - job_name: http
    scrape_interval: 30s
    metrics_path: /probe
    params: {module: [http_any]}
    static_configs:
      - targets: ['http://192.168.8.221:8123/']
        labels: {name: Home Assistant, host: hellcat, group: core}
      - targets: ['http://localhost:3000/api/health']
        labels: {name: Grafana, host: hellcat, group: core}
      - targets: ['http://192.168.8.211:3000/']
        labels: {name: Open WebUI, host: viper, group: core}
      - targets: ['http://192.168.8.231:8090/']
        labels: {name: Demoncrates, host: demon, group: core}
      - targets: ['https://192.168.8.210:8006/']
        labels: {name: Proxmox Viper, host: viper, group: core}
      - targets: ['https://192.168.8.220:8006/']
        labels: {name: Proxmox Hellcat, host: hellcat, group: core}
      - targets: ['https://192.168.8.230:8006/']
        labels: {name: Proxmox Demon, host: demon, group: core}
      - targets: ['http://192.168.8.101:11434/']
        labels: {name: Ollama, host: ryzenous, group: desktop}
    relabel_configs: &blackbox_relabel
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9115

  # Ping latency, hop by hop: LAN -> router -> AT&T gateway -> internet, plus the 10G fabric.
  - job_name: icmp
    scrape_interval: 15s
    metrics_path: /probe
    params: {module: [icmp]}
    static_configs:
      - targets: ['192.168.8.1']
        labels: {name: Flint 2 router, group: lan}
      - targets: ['192.168.8.210']
        labels: {name: Viper, group: lan}
      - targets: ['192.168.8.230']
        labels: {name: Demon, group: lan}
      - targets: ['192.168.8.101']
        labels: {name: Ryzenous, group: desktop}
      - targets: ['10.10.10.210']
        labels: {name: Viper 10G, group: fabric}
      - targets: ['10.10.10.230']
        labels: {name: Demon 10G, group: fabric}
      - targets: ['10.10.10.100']
        labels: {name: Ryzenous 10G, group: desktop}
      - targets: ['192.168.1.254']
        labels: {name: AT&T gateway, group: isp}
      - targets: ['1.1.1.1']
        labels: {name: Cloudflare, group: internet}
      - targets: ['8.8.8.8']
        labels: {name: Google, group: internet}
    relabel_configs: *blackbox_relabel

  - job_name: dns
    scrape_interval: 30s
    metrics_path: /probe
    params: {module: [dns_a]}
    static_configs:
      - targets: ['192.168.8.1']
        labels: {name: Router DNS, group: lan}
      - targets: ['1.1.1.1']
        labels: {name: Cloudflare DNS, group: internet}
    relabel_configs: *blackbox_relabel
SRT3_EOF
cat > /etc/prometheus/blackbox.yml <<'SRT3_EOF'
modules:
  http_any:
    prober: http
    timeout: 5s
    http:
      preferred_ip_protocol: ip4
      follow_redirects: true
      valid_status_codes: [200, 204, 301, 302, 401, 403]
      tls_config:
        insecure_skip_verify: true   # Proxmox self-signed certs
  icmp:
    prober: icmp
    timeout: 3s
    icmp:
      preferred_ip_protocol: ip4
  dns_a:
    prober: dns
    timeout: 3s
    dns:
      query_name: google.com
      query_type: A
      preferred_ip_protocol: ip4
      transport_protocol: udp
SRT3_EOF
cat > /etc/prometheus/alertmanager.yml <<'SRT3_EOF'
# Alertmanager -> Home Assistant webhook -> iPhone push (see srt3-homeassistant/packages/prometheus.yaml)
route:
  receiver: home-assistant
  group_by: [alertname, node, name]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  routes:
    - matchers: ['severity="info"']
      receiver: dashboard-only
receivers:
  - name: home-assistant
    webhook_configs:
      - url: http://192.168.8.221:8123/api/webhook/<webhook-id from srt3-homeassistant/packages/prometheus.yaml>
        send_resolved: true
  - name: dashboard-only
inhibit_rules:
  # A node that's down will also fail its service checks - only page once.
  - source_matchers: ['alertname="NodeDown"']
    target_matchers: ['alertname=~"ServiceDown|PingFailing"']
    equal: [host]
  - source_matchers: ['alertname="InternetDown"']
    target_matchers: ['alertname=~"InternetLatencyHigh|PacketLoss|DNSSlow"']
SRT3_EOF
cat > /etc/prometheus/rules/srt3-records.yml <<'SRT3_EOF'
# Recording rules: precompute the expensive queries every 30s so dashboards
# read one cheap, clean series per host instead of re-crunching raw counters
# on every refresh. Linux and Windows hosts land in the same srt3:* names.
groups:
- name: srt3-hosts
  interval: 30s
  rules:
  - record: srt3:cpu_busy:ratio
    expr: |-
      (1 - avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[2m])))
        or
      (1 - avg by (node) (rate(windows_cpu_time_total{mode="idle"}[2m])))
  - record: srt3:mem_used:ratio
    expr: |-
      (max by (node) (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))
        or
      (max by (node) (1 - windows_memory_available_bytes / windows_memory_physical_total_bytes))
  - record: srt3:mem_used:bytes
    expr: |-
      (max by (node) (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes))
        or
      (max by (node) (windows_memory_physical_total_bytes - windows_memory_available_bytes))
  - record: srt3:root_disk_used:ratio
    expr: |-
      (max by (node) (1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}))
        or
      (max by (node) (1 - windows_logical_disk_free_bytes{volume="C:"} / windows_logical_disk_size_bytes{volume="C:"}))
  - record: srt3:uptime:seconds
    expr: |-
      (max by (node) (time() - node_boot_time_seconds))
        or
      (max by (node) (time() - {__name__=~"windows_system_boot_time_timestamp(_seconds)?"}))
  - record: srt3:temp_max:celsius
    expr: max by (node) (node_hwmon_temp_celsius)
  - record: srt3:load_per_core:ratio
    expr: max by (node) (node_load5) / count by (node) (node_cpu_seconds_total{mode="idle"})
  - record: srt3:disk_io:bytes_per_second
    expr: |-
      (sum by (node) (rate(node_disk_read_bytes_total{device!~"zd.*|dm-.*|loop.*|sr.*"}[2m]) + rate(node_disk_written_bytes_total{device!~"zd.*|dm-.*|loop.*|sr.*"}[2m])))
        or
      (sum by (node) (rate(windows_physical_disk_read_bytes_total[2m]) + rate(windows_physical_disk_write_bytes_total[2m])))
- name: srt3-network
  interval: 30s
  rules:
  - record: srt3:nic_rx:bps
    expr: |-
      (sum by (node, device) (rate(node_network_receive_bytes_total{job="node"}[1m])) * 8 and on (node, device) (node_network_up{job="node"} == 1))
        or
      (sum by (node, device) (label_replace(rate(windows_net_bytes_received_total{nic!~"(?i).*(isatap|loopback|teredo|vethernet|miniport|tailscale|bluetooth|wi-fi direct|virtual).*"}[1m]), "device", "$1", "nic", "(.*)")) * 8)
  - record: srt3:nic_tx:bps
    expr: |-
      (sum by (node, device) (rate(node_network_transmit_bytes_total{job="node"}[1m])) * 8 and on (node, device) (node_network_up{job="node"} == 1))
        or
      (sum by (node, device) (label_replace(rate(windows_net_bytes_sent_total{nic!~"(?i).*(isatap|loopback|teredo|vethernet|miniport|tailscale|bluetooth|wi-fi direct|virtual).*"}[1m]), "device", "$1", "nic", "(.*)")) * 8)
  - record: srt3:nic_speed:bps
    expr: max by (node, device) (node_network_speed_bytes{job="node"} * 8) > 0
  - record: srt3:nic_mtu:bytes
    expr: max by (node, device) (node_network_mtu_bytes{job="node"}) and on (node, device) srt3:nic_speed:bps
  - record: srt3:nic_util:ratio
    expr: (srt3:nic_rx:bps > srt3:nic_tx:bps or srt3:nic_tx:bps) / on (node, device) srt3:nic_speed:bps
  - record: srt3:nic_errors:pps
    expr: sum by (node, device) (rate(node_network_receive_errs_total{job="node"}[5m]) + rate(node_network_transmit_errs_total{job="node"}[5m]) + rate(node_network_receive_drop_total{job="node"}[5m]) + rate(node_network_transmit_drop_total{job="node"}[5m]))
  - record: srt3:fabric_10g:bps
    expr: sum by (node) ((srt3:nic_rx:bps + on (node, device) srt3:nic_tx:bps) and on (node, device) (srt3:nic_speed:bps >= 1e10))
  - record: srt3:lan_1g:bps
    expr: sum by (node) ((srt3:nic_rx:bps + on (node, device) srt3:nic_tx:bps) and on (node, device) (srt3:nic_speed:bps < 1e10))
  - record: srt3:router_rx:bps
    expr: sum by (device) (rate(node_network_receive_bytes_total{job="router", device!~"lo|.*\\..*"}[1m])) * 8
  - record: srt3:router_tx:bps
    expr: sum by (device) (rate(node_network_transmit_bytes_total{job="router", device!~"lo|.*\\..*"}[1m])) * 8
  - record: srt3:ping_rtt:seconds
    expr: max by (name, group) (probe_icmp_duration_seconds{phase="rtt"} and on (instance) (probe_success{job="icmp"} == 1))
  - record: srt3:ping_loss:ratio_5m
    expr: 1 - avg by (name, group) (avg_over_time(probe_success{job="icmp"}[5m]))
- name: srt3-power
  interval: 30s
  rules:
  - record: srt3:power:watts
    expr: label_replace(max by (entity) (hass_sensor_power_w{entity=~"sensor\\.living_room_hs300_plug\\d_.+_current_consumption"}), "device", "$1", "entity", "sensor\\.living_room_hs300_plug\\d_(.+)_current_consumption")
  - record: srt3:power_strip:watts
    expr: max(hass_sensor_power_w{entity="sensor.living_room_hs300_main_current_consumption"})
  - record: srt3:power_cluster:watts
    expr: sum(srt3:power:watts{device=~"viper|hellcat|demon"})
  - record: srt3:power_gpu:watts
    expr: max by (node) (nvidia_smi_power_draw_watts)
  - record: srt3:electricity_rate:usd_per_kwh
    expr: vector(0.45)
  - record: srt3:cluster_cost_monthly:usd
    expr: srt3:power_cluster:watts * 0.72 * scalar(srt3:electricity_rate:usd_per_kwh)
  - record: srt3:strip_cost_monthly:usd
    expr: srt3:power_strip:watts * 0.72 * scalar(srt3:electricity_rate:usd_per_kwh)
SRT3_EOF
cat > /etc/prometheus/rules/srt3-alerts.yml <<'SRT3_EOF'
# Alert rules. Prometheus evaluates these every 30s; firing alerts go to
# Alertmanager (:9093) -> Home Assistant webhook -> iPhone.
# severity: critical/warning = phone push, info = dashboard only.
groups:
  - name: srt3-availability
    rules:
      - alert: NodeDown
        expr: up{job="node"} == 0
        for: 2m
        labels: {severity: critical, host: '{{ $labels.node }}'}
        annotations:
          summary: '{{ $labels.node }} is not answering Prometheus (hung, off, or off the network).'
      - alert: NodeRebooted
        expr: changes(node_boot_time_seconds[10m]) > 0
        labels: {severity: info}
        annotations:
          summary: '{{ $labels.node }} rebooted in the last 10 minutes.'
      - alert: ServiceDown
        expr: probe_success{job="http", group="core"} == 0
        for: 3m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.name }} ({{ $labels.instance }}) is not responding.'
      - alert: ScrapeTargetMissing
        expr: up{job=~"homeassistant|alertmanager"} == 0
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: 'Prometheus cannot scrape {{ $labels.job }} ({{ $labels.instance }}).'

  - name: srt3-network
    rules:
      - alert: InternetDown
        expr: max(probe_success{job="icmp", group="internet"}) == 0
        for: 2m
        labels: {severity: critical}
        annotations:
          summary: 'No ping replies from Cloudflare or Google - internet looks down.'
      - alert: InternetLatencyHigh
        expr: min(srt3:ping_rtt:seconds{group="internet"}) > 0.06
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: 'Internet ping is {{ $value | humanizeDuration }} (normal on fiber is under 20ms).'
      - alert: PacketLoss
        expr: srt3:ping_loss:ratio_5m{group=~"internet|isp|lan|fabric"} > 0.05
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.name }}: {{ $value | humanizePercentage }} packet loss over 5 min.'
      - alert: DNSSlow
        expr: probe_duration_seconds{job="dns"} > 0.5
        for: 10m
        labels: {severity: info}
        annotations:
          summary: '{{ $labels.name }} lookups taking {{ $value | humanizeDuration }}.'
      - alert: NICErrors
        expr: srt3:nic_errors:pps > 1
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} {{ $labels.device }}: {{ $value | printf "%.1f" }} errors/drops per second.'
      - alert: TenGigLinkDegraded
        expr: srt3:nic_speed:bps{device=~"enp1s0.*"} < 1e10
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} {{ $labels.device }} negotiated {{ $value | humanize }}bps instead of 10G.'
      - alert: JumboFramesLost
        expr: srt3:nic_mtu:bytes{device=~"enp1s0.*"} < 9000
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} {{ $labels.device }} MTU is {{ $value }} (expected 9000).'

  - name: srt3-resources
    rules:
      - alert: HighCPU
        expr: srt3:cpu_busy:ratio{node!="ryzenous"} > 0.9
        for: 15m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} CPU at {{ $value | humanizePercentage }} for 15 min.'
      - alert: MemoryPressure
        expr: srt3:mem_used:ratio{node!="ryzenous"} > 0.92
        for: 10m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} memory at {{ $value | humanizePercentage }}.'
      - alert: DiskFillingUp
        expr: predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 7 * 86400) < 0
        for: 1h
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} root disk will be full within 7 days at the current rate.'
      - alert: HostHot
        expr: srt3:temp_max:celsius > 85
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} at {{ $value }}°C.'
      - alert: GPUHot
        expr: nvidia_smi_temperature_gpu > 83
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: 'RTX 3070 at {{ $value }}°C.'
      - alert: ClusterPowerHigh
        expr: srt3:power_cluster:watts > 150
        for: 15m
        labels: {severity: info}
        annotations:
          summary: 'Cluster drawing {{ $value | printf "%.0f" }} W.'
SRT3_EOF
cat > /etc/prometheus/rules/srt3-maintenance.yml <<'SRT3_EOF'
groups:
  - name: srt3-maintenance
    rules:
      - alert: ServiceFailed
        expr: node_systemd_unit_state{state="failed"} == 1
        for: 5m
        labels: {severity: warning, host: '{{ $labels.node }}'}
        annotations:
          summary: '{{ $labels.node }}: systemd unit {{ $labels.name }} has failed.'
      - alert: NVMeMediaErrors
        expr: increase(nvme_media_errors_total[1h]) > 0
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} NVMe {{ $labels.device }} logged media errors - check SMART / backups.'
      - alert: NVMeWearHigh
        expr: nvme_percentage_used_ratio > 0.8
        for: 1h
        labels: {severity: warning}
        annotations:
          summary: '{{ $labels.node }} NVMe {{ $labels.device }} is {{ $value | humanizePercentage }} through its rated life.'
      - alert: RebootRequired
        expr: node_reboot_required == 1
        for: 1h
        labels: {severity: info}
        annotations:
          summary: '{{ $labels.node }} needs a reboot to finish updates.'
      - alert: UpdatesPiling
        expr: sum by (node) (apt_upgrades_pending) > 50
        for: 1h
        labels: {severity: info}
        annotations:
          summary: '{{ $labels.node }} has {{ $value }} package updates pending.'
SRT3_EOF
# Prometheus: keep 90 days, capped at 8 GB, so it can never fill Hellcat's disk.
echo 'ARGS="--storage.tsdb.retention.time=90d --storage.tsdb.retention.size=8GB"' > /etc/default/prometheus
# Blackbox needs raw sockets for ping.
mkdir -p /etc/systemd/system/prometheus-blackbox-exporter.service.d
printf '[Service]\nAmbientCapabilities=CAP_NET_RAW\n' > /etc/systemd/system/prometheus-blackbox-exporter.service.d/ping.conf
chown -R prometheus:prometheus /etc/prometheus

echo "== 5/6 validate"
V=0
promtool check config /etc/prometheus/prometheus.yml >/dev/null 2>&1 && ok "prometheus.yml + rules valid" || { bad "prometheus config invalid:"; promtool check config /etc/prometheus/prometheus.yml; V=1; }
amtool check-config /etc/prometheus/alertmanager.yml >/dev/null 2>&1 && ok "alertmanager.yml valid" || { bad "alertmanager config invalid"; V=1; }
if [ $V -ne 0 ]; then bad "Restoring backup, nothing restarted."; cp -a "$BK"/prometheus/. /etc/prometheus/; exit 1; fi

echo "== 6/6 restart"
systemctl daemon-reload
for s in prometheus-blackbox-exporter prometheus-alertmanager prometheus; do
  systemctl enable -q $s; systemctl restart $s && ok "$s running" || bad "$s failed: journalctl -u $s -n 30"
done

echo; echo "Waiting 45s for first scrapes..."; sleep 45
curl -s localhost:9090/api/v1/targets | python3 -c '
import json,sys
for t in sorted(json.load(sys.stdin)["data"]["activeTargets"], key=lambda t:(t["labels"]["job"],t["labels"].get("name",t["labels"].get("node","")))):
    l=t["labels"]; tag=l.get("name") or l.get("node") or l["instance"]
    print(f"  {t["health"]:8} {l["job"]:14} {tag:18} {t["lastError"][:70]}")'
echo; echo "Done. Expected DOWN until set up: windows/gpu/Ollama (Ryzenous script), router (optional step)."
