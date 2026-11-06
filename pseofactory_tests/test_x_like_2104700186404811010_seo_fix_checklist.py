"""
Tests for x-like:2104700186404811010 (@TheCoolestCool) 18 SEO fixes: capability matrix
and the deterministic estate_seo_fix_checklist gate, proven on both a clean and a broken dist.
Zero em-dashes. Zero en-dashes.
"""

import json

import pseofactory.audit as audit_mod
from pseofactory.verifier import audit_estate_seo_fix_checklist

DOMAIN = "https://gainhelm.com"
BODY = " ".join(["word"] * 200)
LD = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": "x"})


def _page(h1="Title", lang=' lang="en"', img='<img src="/a.svg" alt="chart">', extra_head="", ld=LD, body=BODY):
    return (
        f"<!DOCTYPE html><html{lang}><head><title>t</title>{extra_head}"
        f'<script type="application/ld+json">{ld}</script></head>'
        f"<body><main><h1>{h1}</h1><p>{body}</p>{img}</main></body></html>"
    )


def _site(tmp_path, pages, sitemap_paths, robots=None, gsc=True):
    for rel, html in pages.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(html, encoding="utf-8")
    locs = "".join(f"<url><loc>{DOMAIN}{p}</loc></url>" for p in sitemap_paths)
    (tmp_path / "sitemap.xml").write_text(f"<urlset>{locs}</urlset>", encoding="utf-8")
    (tmp_path / "robots.txt").write_text(
        robots if robots is not None else f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n",
        encoding="utf-8",
    )
    return tmp_path


def _clean(tmp_path):
    gsc = '<meta name="google-site-verification" content="abc">'
    return _site(tmp_path, {"index.html": _page(extra_head=gsc), "tools/calc/index.html": _page()}, ["/", "/tools/calc/"])


def test_clean_dist_passes(tmp_path):
    rep = audit_estate_seo_fix_checklist(dist_dir=_clean(tmp_path), property_id="gainhelm")
    assert rep["passed"], rep["issues"]


def test_broken_dist_trips_every_gap_gate(tmp_path):
    gsc = '<meta name="google-site-verification" content="abc">'
    pages = {
        "index.html": _page(extra_head=gsc),
        "tools/Bad_Url/index.html": _page(),
        "tools/nolang/index.html": _page(lang=""),
        "tools/noalt/index.html": _page(img='<img src="/a.png">'),
        "tools/nold/index.html": _page(ld="{bad json"),
        "tools/blocking/index.html": _page(extra_head='<script src="https://cdn.example.com/x.js"></script>'),
        "tools/thin/index.html": _page(body="short"),
        "tools/hidden/index.html": _page(extra_head='<meta name="robots" content="noindex">'),
        "staging/index.html": _page(),
        "tools/orphan-from-sitemap/index.html": _page(),
    }
    sm = ["/", "/tools/Bad_Url/", "/tools/nolang/", "/tools/noalt/", "/tools/nold/", "/tools/blocking/",
          "/tools/thin/", "/tools/hidden/", "/staging/"]
    root = _site(tmp_path, pages, sm, robots="User-agent: *\nDisallow: /\n")
    (root / "big.png").write_bytes(b"0" * 400_000)
    text = "\n".join(audit_estate_seo_fix_checklist(dist_dir=root, property_id="gainhelm")["issues"])
    for key in ("readable_urls", "html_lang", "alt_text", "schema_markup", "render_blocking", "no_js_content",
                "noindex_hygiene", "test_pages_hidden", "sitemap: indexable route /tools/orphan-from-sitemap",
                "robots_txt: blanket", "robots_txt: no Sitemap", "image_weight"):
        assert key in text, key


def test_missing_search_console_and_robots(tmp_path):
    root = _site(tmp_path, {"index.html": _page()}, ["/"])
    (root / "robots.txt").unlink()
    text = "\n".join(audit_estate_seo_fix_checklist(dist_dir=root, property_id="gainhelm")["issues"])
    assert "search_console" in text and "robots.txt missing" in text


def test_capability_matrix_covers_all_18():
    m = audit_mod.X_LIKE_2104700186404811010_CAPABILITY_MATRIX
    assert [x["rank"] for x in m] == list(range(1, 19))
    s = audit_mod.evaluate_x_like_2104700186404811010_capability_matrix(include_live_estate_audit=False)
    assert s["total_fixes_evaluated"] == 18
    assert s["new_deterministic_gates_count"] + s["already_solved_in_substrate_count"] == 18


def test_live_tenants_pass_both_audits():
    s = audit_mod.evaluate_x_like_2104700186404811010_capability_matrix()
    for t, rep in s["tenant_reports"].items():
        assert rep["checklist"]["passed"], (t, rep["checklist"]["issues"][:5])
        assert rep["technical"]["passed"], (t, rep["technical"]["issues"][:5])
