"""Smoke tests. The symmetry test is the load-bearing one: a tool advertised
in TOOLS but absent from DISPATCH is a lie told to the model."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from app import copilot, registry, results

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

if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  PASS  {k}"); n += 1
    print(f"\n{n} passed")
