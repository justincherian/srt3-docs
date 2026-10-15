# 1. Hardware

## Cluster nodes

Three Lenovo ThinkCentre M920q tiny PCs run Proxmox VE 8 on Debian and are joined in a single **3-node Proxmox cluster** (quorum 2). Each has a Mellanox ConnectX-3 CX312B dual-port 10GbE NIC.

| Node | RAM | LAN IP | Role | Why |
| --- | --- | --- | --- | --- |
| Viper | 64 GB | 192.168.8.210 | AI | The extra RAM holds model weights for CPU inference or offload |
| Hellcat | 16 GB | 192.168.8.220 | Always-on | Hosts Home Assistant, the service that must not go down |
| Demon | 16 GB | 192.168.8.230 (10G: 10.10.10.230) | Media | Runs Demoncrates; 256 GB NVMe |

## Remote GPU node: Ryzenous

| Spec | Value |
| --- | --- |
| CPU | AMD Ryzen 9 5900X |
| RAM | 64 GB DDR4 |
| GPU | NVIDIA RTX 3070 (8 GB) |
| OS | Windows 11 + WSL2 (Ubuntu 24.04, NVIDIA container toolkit) |
| LAN IP | 192.168.8.101 (Wake-on-LAN enabled) |
| 10G IP | 10.10.10.100 |
| Storage | `E:` is the AI/data drive; the music library lives at `E:\srt3-music` |

Ryzenous is deliberately **not** a Proxmox cluster member. It joins jobs as a GPU and storage target over the 10G link: SMB for the music library (measured ~980 MB/s read, 724 MB/s write), the WSL2 GPU worker for Demucs/CLAP, and llama.cpp RPC for inference.

## Network gear

| Device | Role |
| --- | --- |
| AT&T fiber gateway | Upstream ISP |
| GL.iNet Flint 2 | Router (192.168.8.1), DHCP, Tailscale; Ryzenous's 1G link plugs in here |
| NicGiga S25-0802P | 1G PoE switch; carries the three nodes' 1G links and powers the CRS305 |
| MikroTik CRS305-1G-4S+ | 10G SFP+ switch for the cluster fabric |

## Power

A Kasa HS300 smart strip meters each node individually (plugs 4/5/6 = Viper/Hellcat/Demon). Home Assistant turns those readings into cluster power, energy, and cost sensors. See [Home Assistant GitOps](03-home-assistant-gitops.md).
