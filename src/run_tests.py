import os, sys, importlib.util, glob

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.abspath("."))

passed = failed = 0
for path in sorted(glob.glob("gesture/tests/test_*.py") + glob.glob("voice/tests/test_*.py")):
    modname = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"[LOAD FAIL] {modname}: {e}")
        failed += 1
        continue
    funcs = [getattr(mod, n) for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]
    for fn in funcs:
        try:
            fn()
            print(f"PASS  {modname}.{fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {modname}.{fn.__name__}: {e}")
            failed += 1

print(f"\n=== ALL {passed} PASSED ===" if failed == 0 else f"\n=== {passed} passed, {failed} failed ===")
sys.exit(1 if failed else 0)
