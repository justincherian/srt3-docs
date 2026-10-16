# SRT3: IoT network rules on the Flint 2 (OpenWrt ash). Backs up, applies, verifies.
# - Home Assistant (192.168.8.221) may reach IoT devices; nothing else on LAN may.
# - Hellcat (192.168.8.220) may ping IoT devices (dashboard up/down only).
# - IoT devices still cannot start connections into the LAN (unchanged).
# - Fixed IoT addresses by category: .10-19 power (HS300 .10), .20-29 climate (ecobee .20),
#   .30-39 lighting (KL60 .30), .40-49 media, .50-59 cameras. DHCP pool .100-.249 = uncatalogued.
# Undo: cp /etc/config/firewall.bak-srt3 /etc/config/firewall; cp /etc/config/dhcp.bak-srt3 /etc/config/dhcp; /etc/init.d/firewall reload; /etc/init.d/dnsmasq reload
[ -f /etc/config/firewall.bak-srt3 ] || cp /etc/config/firewall /etc/config/firewall.bak-srt3
[ -f /etc/config/dhcp.bak-srt3 ] || cp /etc/config/dhcp /etc/config/dhcp.bak-srt3
echo "== existing LAN/IoT block rule (for reference):"; uci -q show firewall.@rule[14] | sed 's/^/   /'

uci -q delete firewall.srt3_ha_to_iot; uci -q delete firewall.srt3_ping_iot
uci set firewall.srt3_ha_to_iot=rule
uci set firewall.srt3_ha_to_iot.name='SRT3-HomeAssistant-to-IoT'
uci set firewall.srt3_ha_to_iot.src='lan'
uci set firewall.srt3_ha_to_iot.src_ip='192.168.8.221'
uci set firewall.srt3_ha_to_iot.dest='iot'
uci set firewall.srt3_ha_to_iot.proto='all'
uci set firewall.srt3_ha_to_iot.target='ACCEPT'
uci set firewall.srt3_ping_iot=rule
uci set firewall.srt3_ping_iot.name='SRT3-Hellcat-ping-IoT'
uci set firewall.srt3_ping_iot.src='lan'
uci set firewall.srt3_ping_iot.src_ip='192.168.8.220'
uci set firewall.srt3_ping_iot.dest='iot'
uci set firewall.srt3_ping_iot.proto='icmp'
uci set firewall.srt3_ping_iot.icmp_type='echo-request'
uci set firewall.srt3_ping_iot.target='ACCEPT'
# Put both ahead of any LAN->IoT block rule (rules match in order).
uci reorder firewall.srt3_ha_to_iot=0; uci reorder firewall.srt3_ping_iot=1

for d in "hs300 3C:78:95:F1:6A:C7 192.168.10.10" "ecobee 44:61:32:43:B8:D5 192.168.10.20" "kl60 90:9A:4A:3B:13:AE 192.168.10.30"; do
  set -- $d; s=srt3_iot_$1
  uci -q delete dhcp.$s; uci set dhcp.$s=host; uci set dhcp.$s.name="$1"; uci set dhcp.$s.mac="$2"; uci set dhcp.$s.ip="$3"; uci set dhcp.$s.network='iot'
done
uci commit firewall; uci commit dhcp
/etc/init.d/firewall reload >/dev/null 2>&1; /etc/init.d/dnsmasq reload >/dev/null 2>&1
echo "== active rules:"; nft list ruleset 2>/dev/null | grep -c 'SRT3-' | sed 's/^/   SRT3 rules in firewall: /'
echo "== IoT reservations:"; uci show dhcp | grep -o 'srt3_iot_[a-z0-9]*.ip=.*' | sed 's/^/   /'
echo "== HA -> KL60 bulb test (from router's view, should show the bulb):"; ping -c1 -W1 192.168.10.30 >/dev/null && echo "   bulb answers" || echo "   bulb did not answer to router ping (may just ignore ping)"
echo "Done."
