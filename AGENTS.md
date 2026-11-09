# Autonomous pSEO & GEO Software Factory (`pseofactory`)

**Architecture**: Central Python 3 engine (`/home/ubuntuadmin/projects/pseofactory`) that compiles and deploys read-only tenant sites. Tenants come and go; the current ones are every repo with a `.pseofactory.json`:
- **ProfitHelm** (`/home/ubuntuadmin/projects/profithelm-platform`, `https://profithelm.com`)
- **Prexvo** (`/home/ubuntuadmin/projects/prexvo`, `https://prexvo.com`)
- **GainHelm** (`/home/ubuntuadmin/projects/gainhelm`, `https://gainhelm.com`)
- **LienBond** (`/home/ubuntuadmin/projects/lienbond`, `https://lienbond.com`)

## 1. Cold-Start Workflow (Isolate -> Edit -> Verify -> Ship)
1. **Isolate Worktree**: `/home/ubuntuadmin/projects/.agy/worktree_harness.sh create pseofactory <run_id>` (never edit a tenant repo directly).
2. **Engine Test Suite**: `pytest pseofactory_tests -q`
3. **Department Handoff & Tenant Audit**: `python3 -m pseofactory.cli supervisor --verify-handoffs` and `python3 -m pseofactory.cli audit --property all`
4. **4-Phase Revert Gate (on Bug Fixes)**: `/home/ubuntuadmin/projects/.agy/revert_gate.sh --repo pseofactory "<probe_cmd>"`
5. **Security & Diff Gate**: `pr-gate --repo pseofactory`
6. **Ship E2E (Rebase -> Merge -> Compile Tenants -> Deploy Live)**: `/home/ubuntuadmin/projects/.agy/release_pipeline.sh /home/ubuntuadmin/projects/pseofactory <run_id>`

## 2. Core Platform Invariants
1. **Read-Only Compiled Tenants**: Tenant repos (every repo with a `.pseofactory.json`) are compiled artifacts. Implement all features, templates, calculators, and SEO rules in `pseofactory/`.
2. **Zero-Slop Typography**: Strictly zero em-dashes (U+2014) and zero en-dashes (U+2013) across all Python sources, HTML templates, JSON-LD, and feeds. Use standard ASCII hyphens (`-`).
3. **Multi-Dataset Calculators & GEO**: Every calculator combines `>=2` authoritative datasets with a reactive JS engine (`<100ms`), URL-synced state, a 40-60 word `<aside class="quick-answer">`, and stacked JSON-LD (`SoftwareApplication`, `FAQPage`, `BreadcrumbList`, `Organization`).
4. **Autonomous Monetization** (Arif, 2026-11-07: "I dont want to keep asking about monetization."): affiliate, partner, and checkout monetization runs autonomously; never ask Arif about routine partner, affiliate, or checkout status.
