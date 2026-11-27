# Autonomous pSEO & GEO Software Factory (`pseofactory`)

**Goal**: An AI-powered autonomous software factory (`/home/ubuntuadmin/projects/pseofactory`) with repeatable results. It finds what to build, builds it, verifies it, deploys it, gets it found, earns from it, and learns from the result, with no person in the loop. The engine is the product that lasts; the tenants are what it produces. Revenue is the result of a factory that works better than the rest, not the target of one step. Design every change for 50+ sites (not 4): keep stages independent with fail-closed handoffs, and keep runs fast via file hashes and isolated property lanes.

## 1. Workflow (Isolate -> Edit -> Verify -> Ship)
1. **Isolate Worktree**: `/home/ubuntuadmin/projects/.agy/worktree_harness.sh create pseofactory <run_id>` (never edit a tenant repo directly).
2. **Test**: Run targeted tests while iterating (`PSEUFACTORY_FAST_MODE=1 pytest pseofactory_tests/<file>.py -q`); the full suite takes ~30 min and runs in CI.
3. **Audit & Handoffs**: `python3 -m pseofactory.cli supervisor --verify-handoffs` and `python3 -m pseofactory.cli audit --property all` (already runs isolated headless Chrome by default; do not run `--browser` a second time).
4. **Bug-Fix Proof**: `/home/ubuntuadmin/projects/.agy/revert_gate.sh --repo pseofactory "<probe_cmd>"`
5. **Security & Diff Gate**: `pr-gate --repo pseofactory`
6. **Ship E2E**: `/home/ubuntuadmin/projects/.agy/release_pipeline.sh /home/ubuntuadmin/projects/pseofactory <run_id>`

## 2. Core Platform Invariants
1. **Read-Only Compiled Tenants**: Discover active tenants dynamically via `.pseofactory.json` in `/home/ubuntuadmin/projects/`. Never edit tenant repos directly, and do not add new hardcoded tenant lists (legacy lists remain in the engine). Implement all engine features, templates, asset generators, and SEO rules in `pseofactory/`.
2. **Zero-Slop Typography**: Strictly zero em-dashes (U+2014) and zero en-dashes (U+2013) across all Python sources, HTML templates, JSON-LD, feeds, and docs. Use standard ASCII hyphens (`-`).
3. **Calculator Assets & GEO**: For calculator assets, combine `>=2` authoritative datasets with a reactive JS engine (`<100ms`), hash-synced state (`#hash` + `history.replaceState`), a 40-60 word `<aside class="quick-answer">`, outbound primary-source `.gov` links, visible `<details>` Q&A, and clean JSON-LD (`@graph` with `WebApplication`, `WebPage`, `BreadcrumbList` on interior pages only, and `Organization` `@id` reference pointing to `/` and `/about/`).
4. **Autonomous Monetization**: Affiliate, partner, and checkout monetization (including routine partner and affiliate emails) runs autonomously without asking Arif. Public posts and anything unusual still require Arif's approval.
