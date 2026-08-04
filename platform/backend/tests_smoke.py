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


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  PASS  {k}"); n += 1
    print(f"\n{n} passed")
