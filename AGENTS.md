# Autonomous pSEO & GEO Software Factory (`pseofactory`)

**Architecture**: Central Python 3 engine (`/home/ubuntuadmin/projects/pseofactory`) that compiles and deploys read-only tenant sites:
- **ProfitHelm** (`/home/ubuntuadmin/projects/profithelm-platform`, `https://profithelm.com`)
- **Prexvo** (`/home/ubuntuadmin/projects/prexvo`, `https://prexvo.com`)

## 1. Cold-Start Workflow (Isolate -> Edit -> Verify -> Ship)
1. **Isolate Worktree**: `/home/ubuntuadmin/projects/.agy/worktree_harness.sh create pseofactory <run_id>` (never edit `profithelm-platform` or `prexvo` directly).
2. **Engine Test Suite**: `pytest pseofactory_tests -q`
3. **Tenant Audit (10.0/10.0 Target)**: `python3 -m pseofactory.cli audit --property profithelm` and `python3 -m pseofactory.cli audit --property prexvo`
4. **4-Phase Revert Gate (on Bug Fixes)**: `/home/ubuntuadmin/projects/.agy/revert_gate.sh --repo pseofactory "<probe_cmd>"`
5. **Security & Diff Gate**: `pr-gate --repo pseofactory`
6. **Ship E2E (Rebase -> Merge -> Compile Tenants -> Deploy Live)**: `/home/ubuntuadmin/projects/.agy/release_pipeline.sh /home/ubuntuadmin/projects/pseofactory <run_id>`

## 2. Core Platform Invariants
1. **Read-Only Compiled Tenants**: Tenant directories (`profithelm-platform`, `prexvo`) are compiled artifacts. Implement all features, templates, calculators, and SEO rules in `pseofactory/`.
2. **Zero-Slop Typography**: Strictly zero em-dashes (U+2014) and zero en-dashes (U+2013) across all Python sources, HTML templates, JSON-LD, and feeds. Use standard ASCII hyphens (`-`).
3. **Multi-Dataset Calculators & GEO**: Every calculator combines `>=2` authoritative datasets with a reactive JS engine (`<100ms`), URL-synced state, a 40-60 word `<aside class="quick-answer">`, and stacked JSON-LD (`SoftwareApplication`, `FAQPage`, `BreadcrumbList`, `Organization`).
