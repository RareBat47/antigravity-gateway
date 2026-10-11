import os
from pathlib import Path
import yaml

localapp = Path(os.environ["LOCALAPPDATA"]) / "hermes"
main_cfg = localapp / "config.yaml"
if main_cfg.is_file():
    with open(main_cfg, "r", encoding="utf-8") as f:
        c = yaml.safe_load(f) or {}
    print(f"Main default: provider={c.get('model', {}).get('provider')} model={c.get('model', {}).get('default')}")
    print(f"Main providers: {list(c.get('providers', {}).keys())}")
    print(f"Main fallbacks: {c.get('fallback_providers')}")

prof_dir = localapp / "profiles"
if prof_dir.is_dir():
    for p in prof_dir.iterdir():
        cf = p / "config.yaml"
        if cf.is_file():
            with open(cf, "r", encoding="utf-8") as f:
                c = yaml.safe_load(f) or {}
            m = c.get("model", {})
            print(f"Profile {p.name}: provider={m.get('provider')} model={m.get('default')}")
