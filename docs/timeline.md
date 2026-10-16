# Timeline

The order things were built in. Most of it happened in October 2026.

1. **Hardware.** Three M920q nodes running Proxmox, joined into one 3-node cluster, CX312B NICs, and a CRS305. Each node was given a role: Viper for AI, Hellcat always-on, Demon for media.
2. **10G fabric.** Fixed Viper's NIC (the `mlx4_en` blacklist), set MTU 9000 end to end, reached 9.91 Gbit/s.
3. **RDMA.** A full stack on ConnectX-3: ~1006 MiB/s at ~2.73 µs.
4. **Open WebUI on Viper.** A multi-LLM chat frontend at `.211:3000`.
5. **Distributed inference started.** llama.cpp CUDA+RPC build on Ryzenous (WSL2).
6. **Music library.** yt-dlp puller, Navidrome and Syncthing. Services went on Demon, with storage on Ryzenous `E:\srt3-music`.
7. **Demoncrates.** Ingest and analysis, the GPU worker (Demucs and CLAP), the web app, rekordbox export, and a static IP at `.231`.
8. **Remote access.** Tailscale on the Flint 2.
9. **Home Assistant GitOps.** The `srt3-homeassistant` repo with the Git pull add-on, the Claudey dashboard, HS300 power and cost sensors, and Wake-on-LAN for Ryzenous.
10. **Homelable.** A 27-node network map inside HA.
11. **This repo.** Documentation and diagrams.
12. **Storage path verified and benchmarked.** Confirmed the library share mounts over 10G (`10.10.10.100`). Measured the same share over 1G and 10G: read 118 → ~980 MB/s, write 111 → 724 MB/s.
13. **Observability.** Prometheus, Alertmanager and blackbox on Hellcat. Exporters on every host plus Ryzenous and its RTX 3070, and HS300 power via Home Assistant. 4 Grafana dashboards, 23 alert rules pushed to the iPhone. First catches: Demon's 10G MTU misconfig, duplicate Docker exporters, a dead swap file on Viper. See [doc 6](06-observability.md).
