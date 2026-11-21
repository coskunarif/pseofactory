# Autonomous pSEO & GEO Software Factory (`pseofactory`)

## 0. North Star
`pseofactory` is a fully autonomous software company built for a solo founder. One central Python 3 engine (`/home/ubuntuadmin/projects/pseofactory`) creates, verifies, monetizes, and deploys web assets and sites (calculators today, and new asset types in the future) with zero manual testing:
1. **Autonomous Departments**: Discovery, Monetization, Engineering, Verification, Syndication, and Deployment run independently with strict handoff checks between stages.
2. **Deterministic Accuracy**: Every asset compiles from verified facts and passes fail-closed gates, guaranteeing reliable live output across hundreds of pages without manual QA.
3. **Minutes, Not Days, at Any Scale**: Exact file hashes and isolated property lanes keep builds, checks, and deploys fast as the fleet scales from 4 to 50+ properties.

## 1. Workflow (Isolate -> Edit -> Verify -> Ship)
1. **Isolate Worktree**: `/home/ubuntuadmin/projects/.agy/worktree_harness.sh create pseofactory <run_id>` (never edit a tenant repo directly).
2. **Test**: Run targeted tests in `pseofactory_tests/` while iterating (`pytest pseofactory_tests/<file>.py -q`); the full suite (`pytest pseofactory_tests -q`) takes ~30 min and runs in CI.
3. **Audit & Handoffs**: `python3 -m pseofactory.cli supervisor --verify-handoffs` and `python3 -m pseofactory.cli audit --property all` (already runs isolated headless Chrome by default; do not run `--browser` a second time).
4. **Bug-Fix Proof**: `/home/ubuntuadmin/projects/.agy/revert_gate.sh --repo pseofactory "<probe_cmd>"`
5. **Security & Diff Gate**: `pr-gate --repo pseofactory`
6. **Ship E2E**: `/home/ubuntuadmin/projects/.agy/release_pipeline.sh /home/ubuntuadmin/projects/pseofactory <run_id>`

## 2. Core Platform Invariants
1. **Read-Only Compiled Tenants**: Discover active tenants dynamically via `.pseofactory.json` in `/home/ubuntuadmin/projects/` (tenants come and go; never hardcode tenant lists or edit tenant repos directly). Implement all engine features, templates, asset generators, and SEO rules in `pseofactory/`.
2. **Zero-Slop Typography**: Strictly zero em-dashes (U+2014) and zero en-dashes (U+2013) across all Python sources, HTML templates, JSON-LD, feeds, and docs. Use standard ASCII hyphens (`-`).
3. **Calculator Assets & GEO**: For calculator assets, combine `>=2` authoritative datasets with a reactive JS engine (`<100ms`), URL-synced state, a 40-60 word `<aside class="quick-answer">`, and stacked JSON-LD (`SoftwareApplication`, `FAQPage`, `BreadcrumbList`, `Organization`).
4. **Autonomous Monetization**: Affiliate, partner, and checkout monetization (including routine partner and affiliate emails) runs autonomously without asking Arif. Public posts and anything unusual still require Arif's approval.
