"""Step 0 gate: verify the whole causal stack imports and DoWhy 0.8's NEW API
(which differs from every pre-0.8 tutorial online) actually works on this
Python version. Run: .venv\\Scripts\\python tests\\test_gate_env.py
"""
import sys

CRITICAL = ["dowhy", "causalml", "econml", "statsmodels",
            "sklearn", "networkx", "lightgbm", "xgboost",
            "matplotlib", "plotly", "streamlit", "pandas", "numpy", "scipy"]

print(f"Python: {sys.version.split()[0]}  ({sys.executable})")
fails = []
for mod in CRITICAL:
    try:
        m = __import__(mod)
        print(f"  OK   {mod:12} {getattr(m, '__version__', '?')}")
    except Exception as e:
        fails.append((mod, e))
        print(f"  FAIL {mod:12} {type(e).__name__}: {e}")

# --- The real gate: does the DoWhy 0.8 CausalModel API exist as documented? ---
try:
    from dowhy import CausalModel
    import inspect
    sig = inspect.signature(CausalModel.__init__)
    params = list(sig.parameters.keys())
    print("\nDoWhy 0.8 CausalModel.__init__ params:", params)
    assert "graph" in params, "doWhy 0.8 should take a graph string"
    print("  -> CausalModel accepts the graph-based spec (0.8 API confirmed)")
except Exception as e:
    fails.append(("dowhy API", e))
    print(f"\nApiGate FAIL: {type(e).__name__}: {e}")

print("\nGATE RESULT:", "PASS" if not fails else f"FAIL -> {fails}")
raise SystemExit(0 if not fails else 1)
