#!/usr/bin/env python3
"""SRT3: AdGuard Home (on the Flint 2) -> Prometheus textfile metrics. Runs every minute on Hellcat.
Reads the AdGuard API (no changes). Stats are AdGuard's rolling window (24h by default)."""
import json, os, tempfile, urllib.request
API = 'http://192.168.8.1:3000/control/'
OUT = '/var/lib/prometheus/node-exporter/srt3_adguard.prom'
NAMES = {  # IP -> friendly name for per-client panels
    '192.168.8.101': 'ryzenous', '192.168.8.102': 'macbook', '192.168.8.17': 'iphone',
    '192.168.8.210': 'viper', '192.168.8.220': 'hellcat', '192.168.8.221': 'home-assistant',
    '192.168.8.230': 'demon', '192.168.8.231': 'demoncrates', '192.168.8.211': 'open-webui',
    '192.168.8.237': 'ecobee', '192.168.8.22': 'lg-soundbar', '192.168.8.95': 'hs300',
    '192.168.8.114': 'hisense-tv', '192.168.10.110': 'kl60-bulb', '127.0.0.1': 'router',
}
def esc(s): return str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')[:120]
def get(p): return json.load(urllib.request.urlopen(API + p, timeout=5))
L = []
def m(name, val, help_, labels=None, seen=set()):
    if name not in seen:
        L.append(f'# HELP {name} {help_}'); L.append(f'# TYPE {name} gauge'); seen.add(name)
    lab = '{' + ','.join(f'{k}="{esc(v)}"' for k, v in labels.items()) + '}' if labels else ''
    L.append(f'{name}{lab} {val}')
try:
    st, s = get('status'), get('stats')
    m('adguard_up', 1, 'AdGuard API reachable')
    m('adguard_protection_enabled', int(bool(st.get('protection_enabled'))), 'Filtering on')
    m('adguard_stats_window_hours', s.get('time_units') == 'days' and 24 * len(s.get('dns_queries', [])) or len(s.get('dns_queries', [])), 'Length of AdGuard stats window')
    m('adguard_queries', s.get('num_dns_queries', 0), 'DNS queries in stats window')
    blocked = s.get('num_blocked_filtering', 0) + s.get('num_replaced_safebrowsing', 0) + s.get('num_replaced_parental', 0)
    m('adguard_blocked', blocked, 'Blocked queries in stats window (filters + safe browsing + parental)')
    m('adguard_blocked_malware', s.get('num_replaced_safebrowsing', 0), 'Blocked by safe-browsing (malware/phishing) in window')
    m('adguard_avg_processing_seconds', s.get('avg_processing_time', 0), 'Average DNS processing time')
    for kind, key in (('client', 'top_clients'), ('blocked_domain', 'top_blocked_domains'), ('queried_domain', 'top_queried_domains')):
        for item in (s.get(key) or [])[:15]:
            for k, v in item.items():
                labels = {'client': k, 'name': NAMES.get(k, k)} if kind == 'client' else {'domain': k}
                m(f'adguard_top_{kind}_queries', v, f'Top {kind.replace("_", " ")}s by queries in window', labels)
    hourly = s.get('dns_queries') or []
    if hourly: m('adguard_queries_last_hour', hourly[-1], 'Queries in the most recent hour bucket')
    bh = s.get('blocked_filtering') or []
    if bh: m('adguard_blocked_last_hour', bh[-1], 'Blocked in the most recent hour bucket')
except Exception as e:
    L = ['# HELP adguard_up AdGuard API reachable', '# TYPE adguard_up gauge', 'adguard_up 0']
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(OUT), prefix='.adguard.')
with os.fdopen(fd, 'w') as f: f.write('\n'.join(L) + '\n')
os.chmod(tmp, 0o644); os.replace(tmp, OUT)
