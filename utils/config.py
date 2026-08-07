import json
from pathlib import Path

CONFIG_PATH = Path("config.json")
DEFAULT_CONFIG = {
    "ticket_category": None,
    "staff_role": None,
    "log_channel": None,
    "xp_rewards": {"claim": 10, "close": 15, "rating_multiplier": 2},
    "rank_requirements": {
        "Trainee": 0,
        "Helper": 100,
        "Moderator": 300,
        "Senior Moderator": 700,
        "Manager": 1500,
    },
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    merged = DEFAULT_CONFIG.copy()
    merged.update(data)
    merged["xp_rewards"] = {**DEFAULT_CONFIG["xp_rewards"], **merged.get("xp_rewards", {})}
    merged["rank_requirements"] = {**DEFAULT_CONFIG["rank_requirements"], **merged.get("rank_requirements", {})}
    return merged


def save_config(config: dict) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def get_xp_reward(name: str, default: int = 0) -> int:
    return int(load_config().get("xp_rewards", {}).get(name, default))
