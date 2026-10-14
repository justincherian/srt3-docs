# Conventions for updating srt3-docs

- **New build phase:** add `docs/NN-topic.md` with the next number, link it in the README docs table, and add an entry to `docs/timeline.md`.
- **Phase docs:** follow the same shape: goal, what was done (with numbers), a Mermaid diagram where it helps, status, lessons.
- **Roadmap:** move finished items out of `docs/roadmap.md` into the timeline.
- **Topology:** `assets/topology.svg` is hand-written SVG with light/dark CSS variables. Edit it in place, and keep the text inside the boxes.
- **Accuracy:** record only what was actually done or measured. Mark anything else as planned or in progress.
- **Secrets:** never commit keys, tokens, kubeconfigs or passwords. CI runs gitleaks.
- **Commits:** one commit per phase or correction, with a descriptive message.
