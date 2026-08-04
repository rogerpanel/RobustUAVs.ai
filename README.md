# RobustUAVs.ai — uav-e2e-bench

End-to-end UAV security: a unified two-layer benchmark (**Option C**) and a
composed network→navigation certificate (**Option A**). Target: IEEE SaTML 2027.

**Start here:** `CLAUDE.md` — full project context, data source (Kaggle),
build commands, established facts, model/certificate port status, and the
schedule-mapped roadmap. It bootstraps any collaborator (or Claude Code) from zero.

Data: https://www.kaggle.com/datasets/rogernickanaedevha/uavs-network-and-navigation-end-to-end-security-data
(DOI 10.34740/kaggle/dsv/18346203) — fetch with `python3 data/fetch_kaggle.py`.

Layout: `schema/` (unified schema) · `ingest/` (per-dataset adapters) ·
`models/` (Phase-A M1/M4/M6, ported) · `certificates/` (certificate engine) ·
`patches/` (DATAMUt ε patch) · `third_party/` (unmodified DATAMUt) ·
`results/` · `paper/` · `docs/`.
