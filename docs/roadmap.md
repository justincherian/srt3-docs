# Roadmap

Ordered by dependency: each item makes the next easier.

| # | Item | Why | Notes |
| --- | --- | --- | --- |
| 1 | **Finish distributed inference** | The core HPC/AI goal | Benchmark plan in [doc 5](05-distributed-inference.md) |
| 2 | **Observability, phase 3:** router, logs, inference | Finish the picture | Base stack done ([doc 6](06-observability.md)). Next: Flint 2 exporter (script ready), Loki, Proxmox VE exporter, llama.cpp `/metrics` for tokens/s/W, smart plug for Ryzenous |
| 2b | **Patch the cluster** | 240-289 apt updates pending per host | One node at a time, Hellcat last (hosts HA) |
| 3 | **Tighten Tailscale** | Least privilege | Advertise /32 routes plus port-level ACLs instead of the whole `/24` |
| 4 | **Proxmox HA + shared storage** (cluster already formed) | Survive a node loss: VMs restart on another node | Ceph needs about 4 GB RAM per OSD, tight on 16 GB nodes. Use the spare 2.5" SATA bay or start with ZFS replication |
| 5 | **Kubernetes:** Talos VMs on each node | Distributed-systems fundamentals | 3 control-plane etcd members, an API VIP, Cilium (watch MTU vs. 9000), Gateway API, cert-manager. Reference: [prateekjaindev/homelab](https://github.com/prateekjaindev/homelab) |
| 6 | **GitOps for the cluster:** Argo CD | Same pattern as HA, cluster-wide | |
| 7 | **Slurm + OpenMPI over RDMA** | Classic HPC stack | OSU micro-benchmarks; Ryzenous as a GPU partition |
| 8 | **Ray** (Viper head, Ryzenous worker) | Production ML infrastructure patterns | Ray Serve |
| 9 | **ROS 2 + Foxglove, perception replay** | Perception portfolio | KITTI/nuScenes bags, detection on Triton |

## Hardware wishlist

- A UPS with a NUT integration for Home Assistant
- A smart plug for Ryzenous
- A Zigbee coordinator plus temperature sensors
- An RTX 3090 (24 GB), worth it only if the distributed inference work is happening
