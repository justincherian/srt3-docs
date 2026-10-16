"""Generate SRT3 Grafana dashboards (JSON) for upload via the Grafana HTTP API."""
import json, sys

DS = {"type": "prometheus", "uid": "ffzw4kaxny6f4c"}

# Fixed entity colors (validated dark-mode categorical slots, assigned in order).
COLORS = {
    "viper": "#3987e5", "hellcat": "#d95926", "demon": "#199e70",
    "ryzenous": "#c98500", "flint2": "#d55181",
    "tv": "#9085e9", "soundbar": "#e66767", "xbox": "#008300",
}
GREEN, YELLOW, ORANGE, RED = "green", "#EAB839", "orange", "red"


def thr(*steps):
    """thr(GREEN, (0.7, ORANGE), (0.9, RED))"""
    out = [{"color": steps[0], "value": None}]
    out += [{"color": c, "value": v} for v, c in steps[1:]]
    return {"mode": "absolute", "steps": out}


def entity_overrides(names=COLORS):
    o = []
    for n, c in names.items():
        o.append({"matcher": {"id": "byRegexp", "options": f"^{n}( .*)?$"},
                  "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": c}}]})
    return o


class Dash:
    def __init__(self, uid, title, desc, tags=("srt3",), refresh="30s", time_from="now-6h"):
        self.uid, self.title, self.desc = uid, title, desc
        self.tags, self.refresh, self.time_from = list(tags), refresh, time_from
        self.panels, self.vars, self.ann = [], [], []
        self._id = 0
        self.y = 0

    def nid(self):
        self._id += 1
        return self._id

    def target(self, expr, legend="", ref="A", instant=False, fmt=None, interval=None):
        t = {"refId": ref, "expr": expr, "legendFormat": legend, "datasource": DS}
        if instant:
            t["instant"] = True; t["range"] = False
        if fmt:
            t["format"] = fmt
        if interval:
            t["interval"] = interval
        return t

    def targets(self, q):
        if isinstance(q, str):
            q = [(q, "")]
        return [self.target(e, l, chr(65 + i)) for i, (e, l) in enumerate(q)]

    def row(self, title, collapsed=False, repeat=None, inner=None):
        p = {"id": self.nid(), "type": "row", "title": title, "collapsed": collapsed,
             "gridPos": {"x": 0, "y": self.y, "w": 24, "h": 1}, "panels": inner or []}
        if repeat:
            p["repeat"] = repeat
        self.panels.append(p)
        self.y += 1
        return p

    def add(self, p, x, w, h, newline=True):
        p["id"] = self.nid()
        p["gridPos"] = {"x": x, "y": self.y, "w": w, "h": h}
        p.setdefault("datasource", DS)
        self.panels.append(p)
        if newline:
            self.y += h
        return p

    def build(self):
        return {
            "uid": self.uid, "title": self.title, "description": self.desc, "tags": self.tags,
            "timezone": "browser", "refresh": self.refresh, "schemaVersion": 39,
            "time": {"from": self.time_from, "to": "now"},
            "graphTooltip": 1,  # shared crosshair across panels
            "fiscalYearStartMonth": 0, "liveNow": False, "editable": True,
            "links": [{"title": "SRT3", "type": "dashboards", "tags": ["srt3"], "asDropdown": False,
                       "includeVars": False, "keepTime": True, "targetBlank": False, "icon": "external link"}],
            "templating": {"list": self.vars},
            "annotations": {"list": [
                {"builtIn": 1, "datasource": {"type": "grafana", "uid": "-- Grafana --"}, "enable": True,
                 "hide": True, "iconColor": "rgba(0, 211, 255, 1)", "name": "Annotations & Alerts",
                 "type": "dashboard"}] + self.ann},
            "panels": self.panels,
        }


# ---------- panel factories ----------

def ts(d, title, q, unit, desc="", stack=False, fill=8, minv=None, maxv=None, thresholds=None,
       overrides=None, legend_calcs=("lastNotNull", "max"), legend="table", line=2, decimals=None,
       neg_y=None):
    defaults = {"unit": unit, "custom": {
        "drawStyle": "line", "lineWidth": line, "fillOpacity": fill, "gradientMode": "opacity",
        "showPoints": "never", "spanNulls": 60000, "lineInterpolation": "smooth",
        "axisBorderShow": False, "axisSoftMin": 0,
        "stacking": {"mode": "normal" if stack else "none", "group": "A"},
        "thresholdsStyle": {"mode": "dashed" if thresholds else "off"}},
        "color": {"mode": "palette-classic"}}
    if minv is not None: defaults["min"] = minv
    if maxv is not None: defaults["max"] = maxv
    if decimals is not None: defaults["decimals"] = decimals
    if thresholds: defaults["thresholds"] = thresholds
    ov = entity_overrides() + (overrides or [])
    if neg_y:
        ov.append({"matcher": {"id": "byRegexp", "options": neg_y},
                   "properties": [{"id": "custom.transform", "value": "negative-Y"}]})
    return {"type": "timeseries", "title": title, "description": desc,
            "fieldConfig": {"defaults": defaults, "overrides": ov},
            "options": {"legend": {"displayMode": legend, "placement": "bottom" if legend == "list" else "right",
                                   "calcs": list(legend_calcs) if legend == "table" else [], "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}},
            "targets": d.targets(q)}


def stat(d, title, q, unit, desc="", thresholds=None, color_mode="value", graph="area",
         decimals=None, mappings=None, links=None, text_mode="auto", no_value=None, instant=False):
    defaults = {"unit": unit, "thresholds": thresholds or thr(GREEN), "color": {"mode": "thresholds"}}
    if decimals is not None: defaults["decimals"] = decimals
    if mappings: defaults["mappings"] = mappings
    if links: defaults["links"] = links
    if no_value is not None: defaults["noValue"] = no_value
    tg = d.targets(q)
    if instant:
        for t in tg: t["instant"] = True; t["range"] = False
    return {"type": "stat", "title": title, "description": desc,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": color_mode, "graphMode": graph, "textMode": text_mode,
                        "justifyMode": "center", "orientation": "auto", "wideLayout": True,
                        "showPercentChange": False},
            "targets": tg}


def bars(d, title, q, unit, desc="", thresholds=None, minv=0, maxv=None, links=None, mode="gradient",
         sort=None, decimals=None):
    defaults = {"unit": unit, "min": minv, "thresholds": thresholds or thr(GREEN),
                "color": {"mode": "thresholds"}}
    if maxv is not None: defaults["max"] = maxv
    if links: defaults["links"] = links
    if decimals is not None: defaults["decimals"] = decimals
    tg = d.targets(q)
    for t in tg: t["instant"] = True; t["range"] = False
    p = {"type": "bargauge", "title": title, "description": desc,
         "fieldConfig": {"defaults": defaults, "overrides": []},
         "options": {"displayMode": mode, "orientation": "horizontal", "showUnfilled": True,
                     "valueMode": "color", "namePlacement": "left", "sizing": "auto", "minVizHeight": 16,
                     "maxVizHeight": 28,
                     "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
         "targets": tg}
    if sort:
        p["transformations"] = [{"id": "sortBy", "options": {"sort": [{"field": sort, "desc": True}]}}]
    return p


def gauge(d, title, q, unit, minv, maxv, thresholds, desc="", decimals=None):
    defaults = {"unit": unit, "min": minv, "max": maxv, "thresholds": thresholds,
                "color": {"mode": "thresholds"}}
    if decimals is not None: defaults["decimals"] = decimals
    return {"type": "gauge", "title": title, "description": desc,
            "fieldConfig": {"defaults": defaults, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "showThresholdMarkers": True, "showThresholdLabels": False, "minVizHeight": 75},
            "targets": d.targets(q)}


UPDOWN = [{"type": "value", "options": {"0": {"text": "DOWN", "color": RED, "index": 0},
                                         "1": {"text": "UP", "color": GREEN, "index": 1}}}]


def timeline(d, title, q, desc="", mappings=UPDOWN):
    return {"type": "state-timeline", "title": title, "description": desc,
            "fieldConfig": {"defaults": {"mappings": mappings, "color": {"mode": "thresholds"},
                                         "thresholds": thr(RED, (1, GREEN)),
                                         "custom": {"fillOpacity": 85, "lineWidth": 0}},
                            "overrides": []},
            "options": {"showValue": "never", "mergeValues": True, "rowHeight": 0.8,
                        "alignValue": "left", "legend": {"showLegend": False},
                        "tooltip": {"mode": "single"}},
            "targets": d.targets(q)}


def text(md, title=""):
    return {"type": "text", "title": title, "options": {"mode": "markdown", "content": md},
            "datasource": None}


def table(d, title, targets, desc="", organize=None, overrides=None, unit=None, merge=True):
    tf = []
    if merge and len(targets) > 1:
        tf.append({"id": "merge", "options": {}})
    if organize:
        tf.append({"id": "organize", "options": organize})
    defaults = {"custom": {"align": "auto", "cellOptions": {"type": "auto"}, "filterable": False}}
    if unit: defaults["unit"] = unit
    return {"type": "table", "title": title, "description": desc,
            "fieldConfig": {"defaults": defaults, "overrides": overrides or []},
            "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}},
            "transformations": tf, "targets": targets}


def colored_cell(name, display, unit=None, thresholds=None, mode="color-background", decimals=None,
                 width=None):
    props = [{"id": "displayName", "value": display}]
    if unit: props.append({"id": "unit", "value": unit})
    if decimals is not None: props.append({"id": "decimals", "value": decimals})
    if thresholds:
        props += [{"id": "thresholds", "value": thresholds},
                  {"id": "custom.cellOptions", "value": {"type": mode, "mode": "gradient"}
                   if mode == "color-background" else {"type": mode}}]
    if width: props.append({"id": "custom.width", "value": width})
    return {"matcher": {"id": "byName", "options": name}, "properties": props}


def host_link(title="Open {{node}} detail"):
    return [{"title": "Host detail: ${__field.labels.node}",
             "url": "/d/srt3-host/srt3-host-detail?var-node=${__field.labels.node}&${__url_time_range}"}]


PCT = thr(GREEN, (0.7, ORANGE), (0.9, RED))
TEMP = thr(GREEN, (70, ORANGE), (85, RED))

ANN_REBOOT = {"datasource": DS, "enable": True, "hide": False, "iconColor": "#d95926", "name": "Reboots",
              "expr": "changes(node_boot_time_seconds{job=\"node\"}[2m]) > 0", "step": "60s",
              "titleFormat": "{{node}} rebooted", "textFormat": "Boot time changed", "tagKeys": "node",
              "useValueForTime": False}
ANN_ALERTS = {"datasource": DS, "enable": True, "hide": False, "iconColor": "red", "name": "Alerts firing",
              "expr": "ALERTS{alertstate=\"firing\", severity!=\"info\"}", "step": "60s",
              "titleFormat": "{{alertname}}", "textFormat": "{{node}}{{name}}", "tagKeys": "severity",
              "useValueForTime": False}

# ======================================================================
# 1. OVERVIEW (home)
# ======================================================================
def overview():
    d = Dash("srt3-overview", "SRT3 Overview",
             "Home screen: is everything up, how hard is it working, what does it cost. Click any host bar to drill down.")
    d.ann = [ANN_REBOOT, ANN_ALERTS]
    alerts_link = [{"title": "Open alert list", "url": "/alerting/list"}]

    # --- headline numbers
    d.add(stat(d, "Active alerts", "count(ALERTS{alertstate=\"firing\", severity!=\"info\"}) or vector(0)", "none",
               "Alerts currently firing (critical + warning). These also push to your iPhone through Home Assistant. Click to open the alert list.",
               thr(GREEN, (1, RED)), color_mode="background", graph="none", links=alerts_link), 0, 4, 4, False)
    d.add(stat(d, "Cluster power", "srt3:power_cluster:watts", "watt",
               "Viper + Hellcat + Demon, from the HS300 outlets. Sparkline = trend over the time range.",
               thr(GREEN, (80, ORANGE), (150, RED)), decimals=1), 4, 4, 4, False)
    d.add(stat(d, "Cluster cost / month", "srt3:cluster_cost_monthly:usd", "currencyUSD",
               "Projected: current draw x 720 h x $0.45/kWh (PG&E blended). Change the rate in /etc/prometheus/rules/srt3-records.yml.",
               thr(GREEN, (30, ORANGE), (60, RED)), decimals=2), 8, 4, 4, False)
    d.add(stat(d, "Internet ping", "min(srt3:ping_rtt:seconds{group=\"internet\"})", "s",
               "Best round-trip to Cloudflare / Google from Hellcat. AT&T fiber is normally 3-15 ms.",
               thr(GREEN, (0.03, ORANGE), (0.06, RED)), decimals=1), 12, 4, 4, False)
    d.add(stat(d, "Packet loss (5 min)", "max(srt3:ping_loss:ratio_5m{group=\"internet\"})", "percentunit",
               "Share of internet pings that got no reply in the last 5 minutes.",
               thr(GREEN, (0.01, ORANGE), (0.05, RED)), decimals=1), 16, 4, 4, False)
    d.add(stat(d, "10G fabric traffic", "sum(srt3:fabric_10g:bps)", "bps",
               "Sum of rx+tx on all NICs negotiated at 10 Gbit/s (Mellanox CX312B on the CRS305).",
               thr(GREEN), decimals=1), 20, 4, 4)

    d.add(timeline(d, "Up / down history", [
        ("up{job=\"node\", node!=\"\"}", "{{node}}"),
        ("up{job=\"windows\"}", "ryzenous"),
        ("up{job=\"gpu\"}", "ryzenous GPU"),
        ("probe_success{job=\"http\"}", "{{name}}"),
        ("max by (name) (probe_success{job=\"icmp\", group=\"internet\"})", "internet: {{name}}"),
        ("max by (name) (probe_success{job=\"icmp\", group=\"iot\"})", "iot: {{name}}"),
    ], "Green = answering, red = not. Hosts come from Prometheus scrapes; services from HTTP checks every 30s; internet from pings. Ryzenous and Ollama go red whenever the desktop sleeps - that's expected."),
          0, 24, 11)

    # --- hosts
    d.row("Hosts  (click a bar to drill into that host)")
    d.add(bars(d, "CPU busy", [("srt3:cpu_busy:ratio", "{{node}}")], "percentunit",
               "Share of CPU time not idle, averaged over all cores, last 2 min.", PCT, maxv=1, links=host_link(),
               decimals=0), 0, 6, 7, False)
    d.add(bars(d, "Memory used", [("srt3:mem_used:ratio", "{{node}}")], "percentunit",
               "RAM in use (excludes reclaimable cache). On Proxmox this includes VM memory.", PCT, maxv=1,
               links=host_link(), decimals=0), 6, 6, 7, False)
    d.add(bars(d, "Root disk used", [("srt3:root_disk_used:ratio", "{{node}}")], "percentunit",
               "/ on Linux, C: on Ryzenous. An alert fires if the trend says it'll be full within 7 days.",
               thr(GREEN, (0.8, ORANGE), (0.9, RED)), maxv=1, links=host_link(), decimals=0), 12, 6, 7, False)
    d.add(bars(d, "Hottest sensor", [("srt3:temp_max:celsius", "{{node}}")], "celsius",
               "Highest hwmon reading per host (CPU package, NVMe, etc). M920q throttles near 100 °C.", TEMP,
               maxv=100, links=host_link(), decimals=0), 18, 6, 7)
    d.add(ts(d, "CPU busy over time", [("srt3:cpu_busy:ratio", "{{node}}")], "percentunit",
             "Recorded every 30s by a recording rule, so this panel is cheap no matter the time range.",
             minv=0, maxv=1, fill=0), 0, 12, 8, False)
    d.add(ts(d, "Memory used over time", [("srt3:mem_used:bytes", "{{node}}")], "bytes",
             "Bytes in use per host. Hellcat (16 GB) runs the Home Assistant VM plus this monitoring stack.",
             fill=0), 12, 12, 8)

    # --- maintenance
    d.row("Maintenance")
    d.add(bars(d, "Package updates pending", [("sum by (node) (apt_upgrades_pending)", "{{node}}")], "none",
               "apt packages with updates available, per Proxmox host (refreshed by a Debian timer every few hours).",
               thr(GREEN, (20, ORANGE), (50, RED)), decimals=0, links=host_link(), mode="basic"), 0, 8, 6, False)
    d.add(bars(d, "NVMe wear", [("max by (node) (nvme_percentage_used_ratio)", "{{node}}")], "percentunit",
               "SMART 'percentage used': how far through its rated write life each boot SSD is.",
               thr(GREEN, (0.5, ORANGE), (0.8, RED)), maxv=1, decimals=0, links=host_link(), mode="basic"), 8, 8, 6, False)
    fs = stat(d, "Failed services", [("node_systemd_unit_state{state=\"failed\"} == 1", "{{node}} · {{name}}")], "none",
              "systemd units in the failed state on any Proxmox host, shown as host · unit. Host Detail lists them too.",
              thr(GREEN, (1, RED)), color_mode="background", graph="none", no_value="None", instant=True)
    fs["options"]["textMode"] = "name"
    d.add(fs, 16, 4, 6, False)
    d.add(stat(d, "Reboot needed", "count(node_reboot_required == 1) or vector(0)", "none",
               "Hosts that installed a kernel/lib update and need a reboot to finish it.", thr(GREEN, (1, ORANGE)),
               color_mode="background", graph="none"), 20, 4, 6)

    # --- security
    d.row("Security")
    sp = stat(d, "SSH password login", [("max by (node) (srt3_ssh_password_auth)", "{{node}}")], "none",
              "Does sshd accept passwords? Key-only is the goal: password guessing becomes impossible.",
              thr(GREEN, (1, ORANGE)), color_mode="background", graph="none", no_value="no data",
              mappings=[{"type": "value", "options": {"0": {"text": "key-only", "index": 0}, "1": {"text": "password ON", "index": 1}}}])
    sp["options"]["textMode"] = "value_and_name"
    d.add(sp, 0, 6, 6, False)
    fl = stat(d, "Failed logins (15 min)", [("sum by (node) (srt3_auth_failures_15m)", "{{node}}")], "none",
              "Failed SSH + Proxmox web logins per host, last 15 minutes. Alert at >10.",
              thr(GREEN, (3, ORANGE), (10, RED)), graph="area", decimals=0)
    fl["options"]["textMode"] = "value_and_name"
    d.add(fl, 6, 6, 6, False)
    d.add(bars(d, "Security updates pending", [("sum by (node) (apt_upgrades_pending{origin=~\".*security.*\"})", "{{node}}")], "none",
               "Packages from Debian's security repo waiting to install. Alert if any wait 3+ days.",
               thr(GREEN, (1, ORANGE), (20, RED)), decimals=0, links=host_link(), mode="basic"), 12, 6, 6, False)
    d.add(stat(d, "DNS blocked (AdGuard, 24h)", "sum(adguard_blocked) / sum(adguard_queries)", "percentunit",
               "Share of DNS lookups AdGuard Home blocked (ads, trackers, malware). Details on the Network dashboard.",
               thr(GREEN), decimals=1, graph="area"), 18, 3, 6, False)
    d.add(stat(d, "Malware/phishing blocked", "sum(adguard_blocked_malware)", "none",
               "Lookups blocked by AdGuard's safe-browsing list in its 24h window. Anything above 0 means a device tried to reach a known-bad domain.",
               thr(GREEN, (1, ORANGE)), color_mode="background", graph="none", decimals=0, no_value="0"), 21, 3, 6)
    d.add(table(d, "Ports reachable from the network", [d.target("srt3_listening_port{addr=\"any\"}", "", "A", True, "table")],
                "Every TCP/UDP port listening on a non-loopback address, per Proxmox host. A port that wasn't here yesterday triggers NewListeningPort.",
                organize={"excludeByName": {"Time": True, "Value": True, "__name__": True, "instance": True, "job": True, "lab": True, "addr": True},
                          "indexByName": {"node": 0, "proto": 1, "port": 2, "process": 3}}), 0, 16, 8, False)
    d.panels[-1]["transformations"].append({"id": "sortBy", "options": {"sort": [{"field": "node"}]}})
    d.add(bars(d, "Open ports per host", [("count by (node) (srt3_listening_port{addr=\"any\"})", "{{node}}")], "none",
               "Fewer is better. Each open port is something an attacker on your network could try.",
               thr(GREEN), decimals=0, links=host_link(), mode="basic"), 16, 8, 8)

    # --- network
    d.row("Network")
    d.add(ts(d, "Ping, hop by hop", [("srt3:ping_rtt:seconds{name=~\"Flint 2 router|AT&T gateway|Cloudflare|Google\"}", "{{name}}")],
             "s", "Round-trip from Hellcat to each hop. If only the internet lines spike, it's the ISP; if the router line spikes too, it's your LAN.",
             fill=0, decimals=1), 0, 12, 8, False)
    d.add(ts(d, "Throughput: 10G fabric vs 1G LAN", [("srt3:fabric_10g:bps", "{{node}} 10G"), ("srt3:lan_1g:bps", "{{node}} 1G")],
             "bps", "rx+tx per host. 10G = Mellanox port on the CRS305; 1G = onboard NIC to the NicGiga/router.", fill=0,
             overrides=[{"matcher": {"id": "byRegexp", "options": ".* 1G$"},
                         "properties": [{"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [6, 4]}}]}]),
          12, 12, 8)
    d.add(bars(d, "Service response time", "probe_duration_seconds{job=\"http\"}", "s",
               "How long each web UI took to answer the last check (30s interval). Down services show in the timeline above.",
               thr(GREEN, (0.5, ORANGE), (2, RED)), decimals=2, mode="basic"), 0, 12, 8, False)
    for t in d.panels[-1]["targets"]: t["legendFormat"] = "{{name}}"
    d.add(bars(d, "Busiest NICs right now", "topk(6, srt3:nic_rx:bps + on(node, device) srt3:nic_tx:bps)", "bps",
               "rx+tx per physical NIC across every host.", thr(GREEN), decimals=1, mode="basic"), 12, 12, 8)
    for t in d.panels[-1]["targets"]: t["legendFormat"] = "{{node}} {{device}}"

    # --- power
    d.row("Power")
    d.add(ts(d, "Power by outlet (HS300)", [("srt3:power:watts", "{{device}}")], "watt",
             "Each HS300 outlet, stacked, so the top edge is the whole strip.", stack=True, fill=55, line=1),
          0, 16, 8, False)
    pie = {"type": "piechart", "title": "Share of strip power (now)",
           "description": "Where the watts are going right now.",
           "fieldConfig": {"defaults": {"unit": "watt", "color": {"mode": "palette-classic"}},
                           "overrides": entity_overrides()},
           "options": {"pieType": "donut", "displayLabels": [],
                       "legend": {"displayMode": "table", "placement": "right", "showLegend": True,
                                  "values": ["value", "percent"]},
                       "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                       "tooltip": {"mode": "single"}},
           "targets": d.targets([("srt3:power:watts", "{{device}}")])}
    d.add(pie, 16, 8, 8)

    # --- GPU
    d.row("GPU - Ryzenous RTX 3070")
    d.add(gauge(d, "GPU utilization", "max(nvidia_smi_utilization_gpu_ratio)", "percentunit", 0, 1,
                thr(GREEN, (0.85, ORANGE)), "Busy share of the GPU's SMs. LLM inference and Demucs show up here.", 0),
          0, 6, 6, False)
    d.add(gauge(d, "VRAM used", "max(nvidia_smi_memory_used_bytes) / max(nvidia_smi_memory_total_bytes)", "percentunit", 0, 1,
                thr(GREEN, (0.75, ORANGE), (0.92, RED)), "8 GB card. A loaded Ollama model sits here even when idle.", 0),
          6, 6, 6, False)
    d.add(gauge(d, "GPU temperature", "max(nvidia_smi_temperature_gpu)", "celsius", 20, 95,
                thr(GREEN, (75, ORANGE), (83, RED)), "", 0), 12, 6, 6, False)
    d.add(gauge(d, "GPU power", "max(nvidia_smi_power_draw_watts)", "watt", 0, 240,
                thr(GREEN, (180, ORANGE), (220, RED)), "Board power from nvidia-smi (3070 limit is about 220 W).", 0),
          18, 6, 6)

    # --- alerts
    d.row("Alerts")
    d.add(table(d, "Firing now", [d.target("ALERTS{alertstate=\"firing\"}", "", "A", instant=True, fmt="table")],
                "Every alert rule currently firing, straight from the ALERTS metric Prometheus keeps. Empty = all good.",
                organize={"excludeByName": {"Time": True, "Value": True, "__name__": True, "alertstate": True,
                                            "job": True, "instance": True, "lab": True, "phase": True},
                          "indexByName": {"alertname": 0, "severity": 1, "node": 2, "name": 3, "device": 4}}),
          0, 24, 6)

    help_md = """### How this stack works

**Exporters** are tiny programs on each machine that publish numbers at `http://host:port/metrics`:
`node_exporter` on Viper/Hellcat/Demon (:9100), `windows_exporter` (:9182) and `nvidia_gpu_exporter` (:9835) on Ryzenous,
Home Assistant's `/api/prometheus` for the HS300, and `blackbox_exporter` on Hellcat, which pings and HTTP-checks things on Prometheus's behalf.

**Prometheus** (Hellcat :9090) *scrapes* (pulls) every target every 15-30 s and stores each number as a time series.
Every series has a name and labels, e.g. `node_network_receive_bytes_total{node="viper", device="enp1s0d1"}`.

**PromQL** is the query language. `rate(x[1m])` turns an ever-increasing counter into a per-second speed. `sum by (node)` groups. `x > 0.9` filters.
Hover the (i) on any panel to see what it measures. Click **Edit** on a panel to see its exact query.

**Recording rules** precompute common queries every 30 s into clean `srt3:*` series (e.g. `srt3:cpu_busy:ratio`), so these dashboards stay fast.
**Alert rules** are PromQL conditions with a duration (`for: 5m`). Firing alerts go to **Alertmanager** (:9093), which de-duplicates, groups and sends them to Home Assistant, which pushes them to your phone.

**Grafana** (here) only draws. Try these: drag-select on any graph to zoom; press `Esc` to back out; change the time range top-right;
hover one graph and the crosshair follows on all of them; click a host bar to drill down; the orange/red markers on graphs are reboots and alerts.
Explore (compass icon, left menu) is a blank query scratchpad. Try `srt3:` and let autocomplete show you everything."""
    d.row("How this works", collapsed=True, inner=[
        dict(text(help_md), id=900, gridPos={"x": 0, "y": d.y + 1, "w": 24, "h": 14})])
    return d.build()


# ======================================================================
# 2. HOST DETAIL ($node)
# ======================================================================
def host():
    d = Dash("srt3-host", "SRT3 Host Detail", "One machine in depth. Pick the host top-left, or arrive here by clicking a host on the Overview.")
    d.vars = [{"name": "node", "label": "Host", "type": "query", "datasource": DS,
               "query": {"query": "label_values(srt3:cpu_busy:ratio, node)", "refId": "q"},
               "definition": "label_values(srt3:cpu_busy:ratio, node)", "refresh": 2, "sort": 1,
               "current": {"text": "viper", "value": "viper"}, "includeAll": False, "multi": False}]
    d.ann = [ANN_REBOOT]
    N = 'node="$node"'
    d.add(stat(d, "CPU", f"srt3:cpu_busy:ratio{{{N}}}", "percentunit", "", PCT, decimals=0), 0, 3, 4, False)
    d.add(stat(d, "Memory", f"srt3:mem_used:ratio{{{N}}}", "percentunit", "", PCT, decimals=0), 3, 3, 4, False)
    d.add(stat(d, "Root disk", f"srt3:root_disk_used:ratio{{{N}}}", "percentunit", "", thr(GREEN, (0.8, ORANGE), (0.9, RED)), decimals=0), 6, 3, 4, False)
    d.add(stat(d, "Hottest sensor", f"srt3:temp_max:celsius{{{N}}}", "celsius", "", TEMP, decimals=0), 9, 3, 4, False)
    d.add(stat(d, "Load / core (5m)", f"srt3:load_per_core:ratio{{{N}}}", "none",
               "Runnable tasks per core. Above 1.0 means work is queuing.", thr(GREEN, (0.8, ORANGE), (1.5, RED)), decimals=2), 12, 3, 4, False)
    d.add(stat(d, "Uptime", f"srt3:uptime:seconds{{{N}}}", "s", "", thr(GREEN), graph="none", decimals=1), 15, 3, 4, False)
    d.add(stat(d, "Outlet power", f"srt3:power:watts{{device=\"$node\"}}", "watt",
               "From this host's HS300 outlet. Ryzenous isn't on the strip yet - see GPU power on the GPU dashboard.",
               thr(GREEN), decimals=1, no_value="not metered"), 18, 3, 4, False)
    d.add(stat(d, "Scrape health", f"up{{{N}}}", "none", "1 = Prometheus is reading this host's exporter.",
               thr(RED, (1, GREEN)), color_mode="background", graph="none",
               mappings=UPDOWN), 21, 3, 4)

    d.add(ts(d, "CPU by mode", [
        (f"sum by (mode) (rate(node_cpu_seconds_total{{{N}, mode!=\"idle\"}}[$__rate_interval])) / scalar(count(node_cpu_seconds_total{{{N}, mode=\"idle\"}}))", "{{mode}}"),
        (f"sum by (mode) (rate(windows_cpu_time_total{{{N}, mode!=\"idle\"}}[$__rate_interval])) / scalar(count(windows_cpu_time_total{{{N}, mode=\"idle\"}}))", "{{mode}}"),
    ], "percentunit", "Stacked share of CPU time. iowait = waiting on disk; steal = hypervisor took it; user/system = real work.",
        stack=True, fill=50, line=1, minv=0), 0, 12, 8, False)
    d.add(ts(d, "Memory", [
        (f"srt3:mem_used:bytes{{{N}}}", "used"),
        (f"max(node_memory_MemTotal_bytes{{{N}}}) or max(windows_memory_physical_total_bytes{{{N}}})", "total"),
        (f"max(node_memory_Cached_bytes{{{N}}} + node_memory_Buffers_bytes{{{N}}})", "page cache (reclaimable)"),
        (f"max(node_zfs_arc_size{{{N}}})", "ZFS ARC"),
    ], "bytes", "Used vs total. ZFS ARC is Proxmox's disk cache; it shrinks when VMs need RAM.", fill=0,
        overrides=[{"matcher": {"id": "byName", "options": "total"},
                    "properties": [{"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [8, 6]}},
                                   {"id": "color", "value": {"mode": "fixed", "fixedColor": "text"}}]}]),
          12, 12, 8)
    d.add(ts(d, "Network per NIC (in up, out down)", [
        (f"srt3:nic_rx:bps{{{N}}}", "{{device}} in"), (f"srt3:nic_tx:bps{{{N}}}", "{{device}} out")],
        "bps", "Receive above zero, transmit mirrored below. nic0 = 1G onboard, enp1s0d1 = 10G Mellanox.",
        fill=10, neg_y=".* out$"), 0, 12, 8, False)
    d.add(ts(d, "Disk throughput", [
        (f"sum by (device) (rate(node_disk_read_bytes_total{{{N}, device!~\"zd.*|dm-.*|loop.*|sr.*\"}}[$__rate_interval]))", "{{device}} read"),
        (f"sum by (device) (rate(node_disk_written_bytes_total{{{N}, device!~\"zd.*|dm-.*|loop.*|sr.*\"}}[$__rate_interval]))", "{{device}} write"),
        (f"sum by (disk) (rate(windows_physical_disk_read_bytes_total{{{N}}}[$__rate_interval]))", "disk {{disk}} read"),
        (f"sum by (disk) (rate(windows_physical_disk_write_bytes_total{{{N}}}[$__rate_interval]))", "disk {{disk}} write"),
    ], "Bps", "Reads above zero, writes below.", fill=10, neg_y=".* write$"), 12, 12, 8)
    d.add(ts(d, "Temperatures", [(f"node_hwmon_temp_celsius{{{N}}}", "{{chip}} {{sensor}}")], "celsius",
             "Every hwmon sensor. Ryzenous CPU temps aren't exposed by Windows; its GPU temp is on the GPU dashboard.",
             fill=0, thresholds=TEMP, decimals=0), 0, 12, 8, False)
    d.add(table(d, "Filesystems", [
        d.target(f"node_filesystem_size_bytes{{{N}, fstype!~\"tmpfs|ramfs\"}}", "", "A", True, "table"),
        d.target(f"1 - node_filesystem_avail_bytes{{{N}, fstype!~\"tmpfs|ramfs\"}} / node_filesystem_size_bytes{{{N}, fstype!~\"tmpfs|ramfs\"}}", "", "B", True, "table"),
        d.target(f"windows_logical_disk_size_bytes{{{N}}}", "", "C", True, "table"),
        d.target(f"1 - windows_logical_disk_free_bytes{{{N}}} / windows_logical_disk_size_bytes{{{N}}}", "", "D", True, "table"),
    ], "Size and fill per mount (Linux) or volume (Windows).",
        organize={"excludeByName": {"Time": True, "__name__": True, "instance": True, "job": True, "node": True,
                                    "device_error": True, "lab": True}},
        overrides=[colored_cell("Value #A", "Size", "bytes"),
                   colored_cell("Value #B", "Used", "percentunit", PCT, "gauge", 0),
                   colored_cell("Value #C", "Size", "bytes"),
                   colored_cell("Value #D", "Used", "percentunit", PCT, "gauge", 0)]), 12, 12, 8)
    d.panels[-1]["transformations"].insert(0, {"id": "merge", "options": {}})
    d.panels[-1]["transformations"] = [t for i, t in enumerate(d.panels[-1]["transformations"])
                                       if not (t["id"] == "merge" and i > 0)]
    d.add(table(d, "Boot drive health (NVMe SMART)", [
        d.target(f"nvme_percentage_used_ratio{{{N}}}", "", "A", True, "table"),
        d.target(f"nvme_temperature_celsius{{{N}}}", "", "B", True, "table"),
        d.target(f"nvme_power_on_hours_total{{{N}}}", "", "C", True, "table"),
        d.target(f"nvme_data_units_written_total{{{N}}} * 512000", "", "D", True, "table"),
        d.target(f"nvme_media_errors_total{{{N}}}", "", "E", True, "table"),
    ], "From the Debian smartmon/nvme textfile collector. Linux hosts only.",
        organize={"excludeByName": {"Time": True, "__name__": True, "instance": True, "job": True, "node": True, "lab": True}},
        overrides=[colored_cell("Value #A", "Wear", "percentunit", thr(GREEN, (0.5, ORANGE), (0.8, RED)), "gauge", 0),
                   colored_cell("Value #B", "Temp", "celsius", decimals=0),
                   colored_cell("Value #C", "Power-on", "h", decimals=0),
                   colored_cell("Value #D", "Written", "bytes", decimals=1),
                   colored_cell("Value #E", "Media errors", "none", thr(GREEN, (1, RED)), "color-text", 0)]), 0, 12, 6, False)
    d.add(stat(d, "Updates pending", f"sum(apt_upgrades_pending{{{N}}})", "none", "", thr(GREEN, (20, ORANGE), (50, RED)),
               graph="none", decimals=0, no_value="n/a"), 12, 4, 6, False)
    d.add(stat(d, "Reboot required", f"max(node_reboot_required{{{N}}})", "none", "", thr(GREEN, (1, ORANGE)),
               color_mode="background", graph="none", no_value="n/a",
               mappings=[{"type": "value", "options": {"0": {"text": "No", "index": 0}, "1": {"text": "Yes", "index": 1}}}]), 16, 4, 6, False)
    d.add(table(d, "Failed services", [d.target(f"node_systemd_unit_state{{{N}, state=\"failed\"}} == 1", "", "A", True, "table")],
                "Empty = all systemd units healthy.",
                organize={"excludeByName": {"Time": True, "Value": True, "__name__": True, "instance": True, "job": True,
                                            "node": True, "lab": True, "state": True, "type": True}}), 20, 4, 6)
    d.add(text("Need every metric there is? **[Node Exporter Full](/d/rYdddlPWk/node-exporter-full)** "
               "is the community dashboard with ~100 Linux panels (Linux hosts only)."), 0, 24, 2)
    return d.build()


# ======================================================================
# 3. NETWORK
# ======================================================================
def network():
    d = Dash("srt3-network", "SRT3 Network",
             "Internet health, hop-by-hop latency, the 10G fabric, every physical NIC, router, and service checks.")
    d.vars = [{"name": "node", "label": "Hosts", "type": "query", "datasource": DS,
               "query": {"query": "label_values(srt3:nic_rx:bps, node)", "refId": "q"},
               "definition": "label_values(srt3:nic_rx:bps, node)", "refresh": 2, "sort": 1,
               "includeAll": True, "multi": True, "current": {"text": ["All"], "value": ["$__all"]}}]
    d.ann = [ANN_ALERTS]

    d.row("Internet")
    d.add(ts(d, "Ping, hop by hop", [("srt3:ping_rtt:seconds{group=~\"lan|isp|internet\", name=~\"Flint 2 router|AT&T gateway|Cloudflare|Google\"}", "{{name}}")],
             "s", "Hellcat -> router -> AT&T gateway -> internet. Whichever hop jumps first is where the problem is.",
             fill=0, decimals=1, thresholds=thr(GREEN, (0.06, RED))), 0, 12, 9, False)
    hm = {"type": "heatmap", "title": "Cloudflare ping distribution",
          "description": "Each column is a time slice; brighter cells = more pings at that latency. A tight bright band = a stable line. Smears upward = jitter.",
          "fieldConfig": {"defaults": {"custom": {"scaleDistribution": {"type": "linear"}}}, "overrides": []},
          "options": {"calculate": True, "calculation": {"yBuckets": {"mode": "count", "value": "24"}},
                      "color": {"mode": "scheme", "scheme": "Oranges", "steps": 64, "exponent": 0.5, "fill": "dark-orange"},
                      "yAxis": {"unit": "s", "decimals": 3, "axisPlacement": "left"},
                      "cellGap": 1, "legend": {"show": True}, "tooltip": {"mode": "single", "yHistogram": True},
                      "rowsFrame": {"layout": "auto"}, "exemplars": {"color": "rgba(255,0,255,0.7)"}},
          "targets": [d.target("probe_icmp_duration_seconds{phase=\"rtt\", name=\"Cloudflare\"}", "rtt", "A", interval="15s")]}
    d.add(hm, 12, 12, 9)
    d.add(ts(d, "Packet loss (5 min rolling)", [("srt3:ping_loss:ratio_5m", "{{name}}")], "percentunit",
             "Share of pings with no reply. Ryzenous shows loss while asleep - expected.", fill=0, minv=0,
             thresholds=thr(GREEN, (0.05, RED))), 0, 12, 8, False)
    d.add(ts(d, "DNS lookup time", [("probe_duration_seconds{job=\"dns\"}", "{{name}}")], "s",
             "Time to resolve google.com via the router and via Cloudflare directly. If the router is much slower, its DNS is the bottleneck.",
             fill=0, decimals=1), 12, 12, 8)

    d.row("10G fabric (MikroTik CRS305)")
    d.add(ts(d, "10G traffic per host", [("srt3:fabric_10g:bps", "{{node}}")], "bps",
             "rx+tx on each 10 Gbit/s NIC. iperf3 peaked at 9.91 Gbit/s - that's the ceiling.", fill=15,
             maxv=None), 0, 12, 8, False)
    d.add(ts(d, "10G fabric ping", [("srt3:ping_rtt:seconds{group=\"fabric\"}", "{{name}}"),
                                     ("srt3:ping_rtt:seconds{name=~\"Viper|Demon\"}", "{{name}} 1G")],
             "s", "Hellcat to the other nodes over 10G vs over the 1G LAN. 10G should be lower and flatter.",
             fill=0, decimals=2), 12, 12, 8)

    inner_y = d.y + 1
    d.row("NICs on $node", repeat="node")
    d.add(ts(d, "$node: traffic per NIC (in up, out down)", [
        ("srt3:nic_rx:bps{node=~\"$node\"}", "{{device}} in"), ("srt3:nic_tx:bps{node=~\"$node\"}", "{{device}} out")],
        "bps", "This row repeats once per host selected in the Hosts dropdown.", fill=10, neg_y=".* out$"), 0, 12, 8, False)
    d.add(bars(d, "$node: link utilization", "srt3:nic_util:ratio{node=~\"$node\"}", "percentunit",
               "Busier direction / negotiated link speed.", PCT, maxv=1, decimals=1), 12, 6, 8, False)
    for t in d.panels[-1]["targets"]: t["legendFormat"] = "{{device}}"
    d.add(ts(d, "$node: errors + drops", [("srt3:nic_errors:pps{node=~\"$node\"}", "{{device}}")], "pps",
             "Should be flat zero. Anything else = bad cable, MTU mismatch, or a struggling driver.", fill=0,
             legend="list"), 18, 6, 8)

    d.row("All physical interfaces")
    d.add(table(d, "Link speed, MTU, utilization", [
        d.target("srt3:nic_speed:bps", "", "A", True, "table"),
        d.target("srt3:nic_mtu:bytes", "", "B", True, "table"),
        d.target("srt3:nic_util:ratio", "", "C", True, "table"),
        d.target("srt3:nic_rx:bps", "", "D", True, "table"),
        d.target("srt3:nic_tx:bps", "", "E", True, "table"),
    ], "Every physical NIC. 10G ports should show 10 Gb/s and MTU 9000; if not, an alert fires.",
        organize={"excludeByName": {"Time": True}, "indexByName": {"node": 0, "device": 1}},
        overrides=[colored_cell("Value #A", "Speed", "bps", thr("text", (1e10, GREEN)), "color-text"),
                   colored_cell("Value #B", "MTU", "none", thr(ORANGE, (9000, GREEN)), "color-text"),
                   colored_cell("Value #C", "Utilization", "percentunit", PCT, "gauge", 1),
                   colored_cell("Value #D", "In", "bps", decimals=1),
                   colored_cell("Value #E", "Out", "bps", decimals=1)]), 0, 24, 7)

    d.row("Router - GL.iNet Flint 2  (needs the optional router step)")
    d.add(ts(d, "Router traffic per interface (in up, out down)", [
        ("srt3:router_rx:bps", "{{device}} in"), ("srt3:router_tx:bps", "{{device}} out")], "bps",
        "WAN = the port to the AT&T gateway. Empty until prometheus-node-exporter-lua is installed on the router.",
        fill=10, neg_y=".* out$"), 0, 16, 8, False)
    d.add(stat(d, "Router exporter", "up{job=\"router\"}", "none", "", thr(RED, (1, GREEN)), color_mode="background",
               graph="none", mappings=UPDOWN, no_value="not installed"), 16, 8, 4, False)
    d.add(stat(d, "Router conntrack entries", "node_nf_conntrack_entries{job=\"router\"}", "none",
               "Open NAT connections through the router.", thr(GREEN), decimals=0, no_value="-"), 16, 8, 4)
    d.panels[-1]["gridPos"]["y"] = d.panels[-2]["gridPos"]["y"] + 4
    d.y = d.panels[-3]["gridPos"]["y"] + 8

    d.row("DNS - AdGuard Home (on the Flint 2)")
    for i, (t, e, u, desc, th) in enumerate([
        ("Queries (24h)", "sum(adguard_queries)", "short", "DNS lookups from every device in AdGuard's 24h window.", thr(GREEN)),
        ("Blocked (24h)", "sum(adguard_blocked)", "short", "Ads, trackers, malware.", thr(GREEN)),
        ("Blocked %", "sum(adguard_blocked) / sum(adguard_queries)", "percentunit", "", thr(GREEN)),
        ("Malware blocked", "sum(adguard_blocked_malware)", "short", "Safe-browsing hits: a device tried a known-bad domain.", thr(GREEN, (1, ORANGE))),
        ("Avg lookup time", "max(adguard_avg_processing_seconds)", "s", "AdGuard's average processing time per query.", thr(GREEN, (0.05, ORANGE), (0.2, RED))),
        ("Protection", "max(adguard_protection_enabled)", "none", "Filtering on/off. 'down' = Hellcat can't reach the AdGuard API.", thr(RED, (1, GREEN)))]):
        st = stat(d, t, e, u, desc, th, decimals=1 if u != "short" else 0, graph="none",
                  color_mode="background" if t in ("Protection", "Malware blocked") else "value")
        if t == "Protection":
            st["fieldConfig"]["defaults"]["mappings"] = [{"type": "value", "options": {"0": {"text": "OFF", "index": 0}, "1": {"text": "ON", "index": 1}}}]
            st["fieldConfig"]["defaults"]["noValue"] = "down"
        d.add(st, i * 4, 4, 4, i == 5)
    d.add(ts(d, "Blocked % over time", [("sum(adguard_blocked) / sum(adguard_queries)", "blocked share (24h window)")], "percentunit",
             "Rolling 24h block rate. A sudden jump can mean a device started phoning home a lot.", fill=10, minv=0), 0, 12, 7, False)
    d.add(ts(d, "Queries in the latest hour", [("max(adguard_queries_last_hour)", "queries"), ("max(adguard_blocked_last_hour)", "blocked")], "short",
             "AdGuard's current hourly bucket.", fill=10), 12, 12, 7)
    d.add(bars(d, "Top clients (24h)", [("topk(12, adguard_top_client_queries)", "{{name}}")], "short",
               "Which devices make the most DNS lookups. IoT devices showing up high here are worth a look.", thr(GREEN), decimals=0, mode="basic"), 0, 8, 10, False)
    d.add(bars(d, "Top blocked domains (24h)", [("topk(12, adguard_top_blocked_domain_queries)", "{{domain}}")], "short", "", thr(GREEN), decimals=0, mode="basic"), 8, 8, 10, False)
    d.add(bars(d, "Top queried domains (24h)", [("topk(12, adguard_top_queried_domain_queries)", "{{domain}}")], "short", "", thr(GREEN), decimals=0, mode="basic"), 16, 8, 10)

    d.row("Services")
    d.add(ts(d, "Response time per service", [("probe_duration_seconds{job=\"http\"}", "{{name}}")], "s",
             "Full HTTP round-trip from Hellcat, every 30s.", fill=0, decimals=2), 0, 12, 8, False)
    d.add(table(d, "Service checks", [
        d.target("probe_success{job=\"http\"}", "", "A", True, "table"),
        d.target("probe_http_status_code{job=\"http\"}", "", "B", True, "table"),
        d.target("(probe_ssl_earliest_cert_expiry{job=\"http\"} - time()) / 86400", "", "C", True, "table"),
    ], "Status, HTTP code, and days until the TLS cert expires (Proxmox self-signed certs last ~2 years).",
        organize={"excludeByName": {"Time": True, "__name__": True, "job": True, "lab": True, "group": True},
                  "indexByName": {"name": 0, "host": 1, "instance": 2}},
        overrides=[colored_cell("Value #A", "Status", None, thr(RED, (1, GREEN)), "color-background"),
                   colored_cell("Value #B", "HTTP"),
                   colored_cell("Value #C", "Cert days left", "none", thr(RED, (14, ORANGE), (30, GREEN)), "color-text", 0)]),
          12, 12, 8)
    d.panels[-1]["fieldConfig"]["overrides"][0]["properties"].append({"id": "mappings", "value": UPDOWN})
    return d.build()


# ======================================================================
# 4. GPU & POWER
# ======================================================================
def gpu_power():
    d = Dash("srt3-gpu-power", "SRT3 GPU & Power",
             "RTX 3070 on Ryzenous in depth, plus per-outlet power, energy and cost.")
    d.row("GPU - RTX 3070 (Ryzenous)")
    d.add(ts(d, "GPU + memory-controller utilization", [
        ("max(nvidia_smi_utilization_gpu_ratio)", "GPU cores"), ("max(nvidia_smi_utilization_memory_ratio)", "memory bus")],
        "percentunit", "Cores = compute busy. Memory bus = VRAM bandwidth busy (LLM token generation is usually memory-bound).",
        minv=0, maxv=1, fill=10), 0, 12, 8, False)
    d.add(ts(d, "VRAM", [("max(nvidia_smi_memory_used_bytes)", "used"), ("max(nvidia_smi_memory_total_bytes)", "total")],
             "bytes", "8 GB. A model that doesn't fit spills to system RAM and gets ~10x slower.", fill=15,
             overrides=[{"matcher": {"id": "byName", "options": "total"},
                         "properties": [{"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [8, 6]}},
                                        {"id": "custom.fillOpacity", "value": 0},
                                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "text"}}]}]),
          12, 12, 8)
    d.add(ts(d, "Power draw vs limit", [("max(nvidia_smi_power_draw_watts)", "draw"),
                                         ("max(nvidia_smi_enforced_power_limit_watts)", "enforced limit")],
             "watt", "When draw hugs the limit, the card is power-throttling.", fill=10,
             overrides=[{"matcher": {"id": "byName", "options": "enforced limit"},
                         "properties": [{"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [8, 6]}},
                                        {"id": "custom.fillOpacity", "value": 0},
                                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "red"}}]}]),
          0, 8, 8, False)
    d.add(ts(d, "Temperature", [("max(nvidia_smi_temperature_gpu)", "GPU core")], "celsius",
             "Alert at 83 °C for 5 min.", fill=0, thresholds=thr(GREEN, (75, ORANGE), (83, RED)), decimals=0), 8, 8, 8, False)
    d.add(ts(d, "Fan speed", [("max(nvidia_smi_fan_speed_ratio)", "fan")], "percentunit", "", fill=0, minv=0, maxv=1),
          16, 8, 8)
    d.add(ts(d, "Clocks", [("max(nvidia_smi_clocks_current_graphics_clock_hz)", "graphics"),
                            ("max(nvidia_smi_clocks_current_memory_clock_hz)", "memory")], "hertz",
             "Clocks drop when idle or throttling.", fill=0), 0, 12, 8, False)
    d.add(timeline(d, "Why is it slowing down? (throttle reasons)", [
        ("max(nvidia_smi_clocks_event_reasons_gpu_idle)", "idle"),
        ("max(nvidia_smi_clocks_event_reasons_sw_power_cap)", "power cap"),
        ("max(nvidia_smi_clocks_event_reasons_sw_thermal_slowdown)", "thermal (sw)"),
        ("max(nvidia_smi_clocks_event_reasons_hw_thermal_slowdown)", "thermal (hw)"),
        ("max(nvidia_smi_clocks_event_reasons_hw_slowdown)", "hw slowdown"),
    ], "Lit bar = that reason is active. Idle is normal. Power cap under load is normal. Thermal is not.",
        mappings=[{"type": "value", "options": {"0": {"text": "no", "color": "transparent", "index": 0},
                                                "1": {"text": "active", "color": ORANGE, "index": 1}}}]),
          12, 12, 8)
    d.row("Power (HS300 strip)")
    d.add(stat(d, "Strip now", "srt3:power_strip:watts", "watt", "Everything on the HS300.", thr(GREEN), decimals=1), 0, 4, 4, False)
    d.add(stat(d, "Cluster now", "srt3:power_cluster:watts", "watt", "Viper + Hellcat + Demon.", thr(GREEN), decimals=1), 4, 4, 4, False)
    d.add(stat(d, "Cluster idle floor (24h)", "min_over_time(srt3:power_cluster:watts[24h])", "watt",
               "Lowest cluster draw in 24h: what the lab costs doing nothing.", thr(GREEN), graph="none", decimals=1), 8, 4, 4, False)
    d.add(stat(d, "Cluster energy (24h)", "avg_over_time(srt3:power_cluster:watts[24h]) * 24 / 1000", "kwatth",
               "Average draw x 24 h.", thr(GREEN), graph="none", decimals=2), 12, 4, 4, False)
    d.add(stat(d, "Cluster $/month", "srt3:cluster_cost_monthly:usd", "currencyUSD", "At current draw, $0.45/kWh.",
               thr(GREEN, (30, ORANGE), (60, RED)), decimals=2), 16, 4, 4, False)
    d.add(stat(d, "Strip $/month", "srt3:strip_cost_monthly:usd", "currencyUSD", "Whole strip at current draw.",
               thr(GREEN, (40, ORANGE), (80, RED)), decimals=2), 20, 4, 4)
    d.add(ts(d, "Per outlet", [("srt3:power:watts", "{{device}}")], "watt", "Unstacked, so you can compare outlets directly.",
             fill=0), 0, 16, 9, False)
    d.add(bars(d, "Energy per outlet, last 24h", "avg_over_time(srt3:power:watts[24h]) * 24 / 1000", "kwatth",
               "kWh per outlet over the last day.", thr(GREEN), decimals=2, mode="basic"), 16, 8, 9)
    for t in d.panels[-1]["targets"]: t["legendFormat"] = "{{device}}"
    d.add(ts(d, "Cluster power vs cluster CPU", [("srt3:power_cluster:watts", "cluster watts")], "watt",
             "Pair with the panel to the right: how many watts does extra CPU work cost?", fill=10), 0, 12, 8, False)
    d.add(ts(d, "Cluster CPU (avg of 3 nodes)", [("avg(srt3:cpu_busy:ratio{node=~\"viper|hellcat|demon\"})", "avg CPU busy")],
             "percentunit", "Same time axis as the power panel - crosshair is shared.", fill=10, minv=0, maxv=1), 12, 12, 8)
    return d.build()


if __name__ == "__main__":
    out = {"overview": overview(), "host": host(), "network": network(), "gpu_power": gpu_power()}
    json.dump(out, open(sys.argv[1], "w"))
    for k, v in out.items():
        print(k, len(v["panels"]), "panels", len(json.dumps(v)), "bytes")
