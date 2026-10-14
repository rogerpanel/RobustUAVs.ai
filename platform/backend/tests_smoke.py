"""Smoke tests. The symmetry test is the load-bearing one: a tool advertised
in TOOLS but absent from DISPATCH is a lie told to the model."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from app import auth, copilot, jobs, registry, results, runners  # noqa: F401

def test_copilot_symmetry():
    assert set(copilot.TOOLS) == set(copilot.DISPATCH), (
        f"advertised-not-dispatchable: {set(copilot.TOOLS) - set(copilot.DISPATCH)}; "
        f"dispatchable-not-advertised: {set(copilot.DISPATCH) - set(copilot.TOOLS)}")

def test_registry_sources_exist():
    missing = [m.model_id for m in registry.REGISTRY
               if not (results.REPO / m.source).exists()]
    assert not missing, f"registry rows with no backing code: {missing}"

def test_every_tool_callable():
    for name in copilot.TOOLS:
        if copilot.TOOLS[name]["params"].get("theta_s"):
            out = copilot.call(name, theta_s=0.25)
        else:
            out = copilot.call(name)
        assert isinstance(out, dict) and ("data" in out or "error" in out), name

def test_runner_schemas_split_params():
    """A runner that lumps everything into params defeats the demo: the point
    is that the audience can see which KIND of knob moved."""
    for kind, r in jobs.RUNNERS.items():
        assert r.params, f"{kind} declares no parameters"
        assert r.hyperparams, f"{kind} declares no hyperparameters"
        overlap = set(r.params) & set(r.hyperparams)
        assert not overlap, f"{kind} declares {overlap} in both panels"
        for name, spec in {**r.params, **r.hyperparams}.items():
            assert "default" in spec, f"{kind}.{name} has no default"
            assert "label" in spec, f"{kind}.{name} has no label"


def test_runs_execute():
    import time
    from app import db
    db.init_db()
    started = jobs.submit("mapping_compare", {"theta_s": 0.25}, {})
    for _ in range(300):
        time.sleep(0.1)
        cur = jobs.get(started["run_id"])
        if cur["status"] in ("done", "failed", "cancelled"):
            break
    assert cur["status"] == "done", cur.get("error")
    rows = cur["result"]["rows"]
    assert {r["mapping"] for r in rows} == {"kinematic", "receiver", "ekf"}
    # The demo's whole point: at the paper operating point they disagree.
    assert cur["result"]["mappings_disagree"] is True


def test_unknown_setting_rejected():
    """Silently ignoring an unknown key would let a demo believe it varied
    something it did not."""
    try:
        jobs.submit("mapping_compare", {"not_a_real_knob": 1}, {})
    except ValueError as exc:
        assert "not_a_real_knob" in str(exc)
    else:
        raise AssertionError("unknown setting was accepted")


def test_auth_open_by_default():
    assert auth.is_open(), "no API_TOKENS set, so writes must be public"


# ------------------------------------------------------------------ papers --
# Driven through the routes, not the module, so the 404/400/422/503 mapping
# in main.py is under test too. No `with` block: the job worker is not needed.

def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_papers_catalogue():
    r = _client().get("/api/papers")
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()["papers"]]
    assert ids == ["I", "II", "III"], ids


def test_papers_result_roundtrip():
    """One result file, as JSON and as the CSV download, must agree."""
    import csv, io
    c = _client()
    papers = [p for p in c.get("/api/papers").json()["papers"] if p["result_files"]]
    if not papers:
        assert c.get("/api/papers/I/results").status_code == 503
        return
    p = papers[0]
    f = p["result_files"][0]
    url = f"/api/papers/{p['id']}/results/{f['name']}"
    js = c.get(url)
    assert js.status_code == 200, js.text
    body = js.json()
    assert body["n_rows"] == len(body["rows"]) == f["rows"]
    raw = c.get(url, params={"format": "csv"})
    assert raw.status_code == 200 and raw.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(raw.text)))
    assert len(rows) == body["n_rows"]
    assert list(rows[0].keys()) == body["columns"] if rows else True
    # Present in the index with the same row count.
    idx = c.get(f"/api/papers/{p['id']}/results").json()
    assert {x["name"]: x["rows"] for x in idx["files"]}[f["name"]] == f["rows"]


def test_papers_traversal_rejected():
    from app import papers
    c = _client()
    for bad in ("%2e%2e/%2e%2e/platform/backend/app/main.py",
                "%2e%2e%2f%2e%2e%2fREADME.md",
                "%2e%2e/%2e%2e/paperI/results/dauth.csv",
                "e5_marl/..%2F..%2F..%2FpaperI%2Fresults%2Fdauth.csv",
                "%2Fetc%2Fpasswd", "logs_r%2F_queue.txt", "x.pt"):
        r = c.get(f"/api/papers/III/results/{bad}")
        assert r.status_code in (400, 404), (bad, r.status_code)
    for bad in ("../../README.md", "../../paperI/results/dauth.csv", "/etc/passwd"):
        try:
            papers.resolve_result("III", bad)
        except papers.PathRejected:
            pass
        else:
            raise AssertionError(f"traversal accepted: {bad}")
    assert c.get("/api/papers/IV/results").status_code == 404


def test_paper1_budget_finite():
    import math
    c = _client()
    r = c.post("/api/papers/I/budget", json={})
    if r.status_code == 503:     # paperI/ not present in this deployment
        return
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d["rho_m"], float) and math.isfinite(d["rho_m"]), d["rho_m"]
    assert d["pass"] == (d["rho_m"] <= d["alert_limit_m"])
    # The unauthenticated default is the paper's own m_min_unauth.
    from app import papers
    try:
        _, rows = papers.read_table(results.REPO / "paperI" / "results" / "parent_table.csv")
    except results.ResultUnavailable:
        rows = []
    ref = [x for x in rows if x["m"] == "m_min_unauth"]
    if ref:
        assert abs(d["rho_m"] - ref[0]["theta_star_s"]) < 1e-3, (d["rho_m"], ref)
        print(f"        rho {d['rho_m']:.4f} m == parent_table m_min_unauth "
              f"{ref[0]['theta_star_s']}")
    assert c.post("/api/papers/I/budget", json={"not_a_knob": 1}).status_code == 422


def test_paper2_corpus_or_503():
    r = _client().get("/api/papers/II/corpus")
    if r.status_code == 503:
        assert r.json()["detail"]["unavailable"].startswith("paperII/")
        return
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["n_filtered"] == len(d["rows"]) <= d["n_total"]


def test_paper3_certify_tiny():
    """Hand computation: rho = (1,3,6,12), alpha = (2,5,5,10).
    n_k = #{rho <= alpha_(k)} = (1,2,2,3); k - n_k = (0,0,1,1); d = 1.
    Collapsing the b = 1 best agent gives n = (0,1,1,2), so d = 2."""
    c = _client()
    r = c.post("/api/papers/III/certify",
               json={"rho": [1, 3, 6, 12], "alpha": [2, 5, 5, 10], "b": 1,
                     "proposal": [0, 1, 2, 3]})
    if r.status_code == 503:
        return
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["count_profile"] == [1, 2, 2, 3]
    assert d["deficiency"] == 1 and d["max_coverage"] == 3
    assert d["coverage_margin"] == -1
    assert d["worst_case_deficiency"] == 2
    assert d["greedy_covered"] == 3 == d["projection"]["covered"]
    too_big = c.post("/api/papers/III/certify", json={"rho": [1.0] * 2001, "alpha": [2.0]})
    assert too_big.status_code == 422


def test_paper3_lift_probability():
    r = _client().post("/api/papers/III/lift",
                       json={"N": 12, "alpha": [2, 5, 5, 10, 10, 20, 20, 20],
                             "q": [0.7, 0.05, 0.05, 0.05, 0.15]})
    if r.status_code == 503:
        return
    assert r.status_code == 200, r.text
    assert 0.0 <= r.json()["p_full"] <= 1.0


def test_paper3_marl_tables():
    r = _client().get("/api/papers/III/marl")
    if r.status_code == 503:
        return
    assert r.status_code == 200, r.text
    assert "e5_marl" in r.json()["tables"], r.json()["dirs"]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  PASS  {k}"); n += 1
    print(f"\n{n} passed")
