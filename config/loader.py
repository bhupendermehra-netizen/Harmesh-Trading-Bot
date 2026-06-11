import json
import os
from pathlib import Path


def load_config(path=None):
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_strategy_config(name=None):
    cfg = load_config()
    if cfg is None:
        return {}
    strategies = cfg.get("trading", {}).get("strategies", {})
    if name:
        return strategies.get(name, {})
    return strategies
