# SRT3 Homelab

A three-node Proxmox cluster of mini PCs with a 10G fabric and a remote GPU desktop. It's built to develop skills in distributed systems, HPC networking and AI inference, and to run real services day to day.

![SRT3 topology](assets/topology.svg)

## At a glance

| Node | Hardware | Role | Runs |
| --- | --- | --- | --- |
| **Viper** | Lenovo M920q · 64 GB | AI node | Open WebUI (`.211:3000`), llama.cpp RPC host (in progress) |
| **Hellcat** | Lenovo M920q · 16 GB | Always-on | Home Assistant VM (`.221:8123`): Claudey dashboard, Homelable, power metering |
| **Demon** | Lenovo M920q · 16 GB · 256 GB NVMe | Media | Demoncrates LXC (`.231`): AI DJ library, Navidrome, Syncthing, Grafana |
| **Ryzenous** | Ryzen 9 5900X · 64 GB · RTX 3070 | GPU + storage (not in cluster) | Music library on `E:`, Demucs/CLAP GPU worker, Ollama, llama.cpp CUDA+RPC |

**Network:**
- **10G fabric:** a MikroTik CRS305 with Mellanox CX312B NICs, jumbo frames (MTU 9000), and RDMA.
- **1G LAN:** a GL.iNet Flint 2 router and a NicGiga PoE switch.
- **Remote access:** Tailscale.

## Results so far

| Metric | Value |
| --- | --- |
| TCP throughput over 10G (iperf3, MTU 9000) | **9.91 Gbit/s** |
| RDMA bandwidth | **~1006 MiB/s** |
| RDMA latency | **~2.73 µs** |
| SMB library share, 1G → 10G | read **118 → ~980 MB/s** (8.3×), write **111 → 724 MB/s** (6.5×) |
| Demoncrates library | ~170 tracks across 6 crates |

## Docs

| # | Topic | What's in it |
| --- | --- | --- |
| 1 | [Hardware](docs/01-hardware.md) | Node specs, roles, why each node does what |
| 2 | [10G networking + RDMA](docs/02-networking-10g-rdma.md) | Recovering the CX312B, jumbo frames, RDMA results, remote access |
| 3 | [Home Assistant GitOps](docs/03-home-assistant-gitops.md) | Claude → GitHub → HA pull loop, Claudey dashboard, power metering |
| 4 | [Demoncrates](docs/04-demoncrates.md) | Self-hosted AI DJ pipeline across Demon and Ryzenous |
| 5 | [Distributed inference](docs/05-distributed-inference.md) | llama.cpp RPC across Ryzenous and Viper (in progress) |
| 6 | [Observability](docs/06-observability.md) | Prometheus + Grafana + Alertmanager, 4 dashboards, phone alerts, issues it caught |
| — | [Timeline](docs/timeline.md) | What got built, in order |
| — | [Roadmap](docs/roadmap.md) | What's next |

## Conventions

- **No secrets in this repo.** Keys, tokens, kubeconfigs and passwords stay on the hosts. CI runs gitleaks on every push.
- **IP addresses are LAN-only (`192.168.8.0/24`, `10.10.10.0/24`).** They're documented because the repo is private. Scrub them before making it public.
- **Diagrams:** the topology is a hand-written SVG in `assets/`. Flow diagrams are Mermaid, which GitHub renders inline, so you can edit them as text.

## Keeping it current

This repo is updated as the lab changes. Each new build phase gets its own `docs/NN-topic.md`, an entry in the [timeline](docs/timeline.md), and an updated row in the [roadmap](docs/roadmap.md). The topology SVG changes whenever the hardware or network does. See [CLAUDE.md](CLAUDE.md) for the conventions.
