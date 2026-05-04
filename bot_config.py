"""
Shared mutable configuration for the Reze Bot.
Both main.py and dashboard.py read/write from this module.
All runtime-tunable values live here so the dashboard can modify them on the fly.
"""

import threading

_lock = threading.Lock()

config = {
    # --- Rate Limiting ---
    "rate_limit_count": 5,
    "rate_limit_window": 40,

    # --- Grudge System ---
    "grudge_trigger_count": 4,
    "grudge_trigger_window": 60,
    "grudge_duration_min": 300,
    "grudge_duration_max": 600,

    # --- Media Pipeline ---
    "image_cooldown_min": 2,
    "image_cooldown_max": 4,
    "max_files_per_message": 3,
    "max_file_size_mb": 8,

    # --- Human Behavior Probabilities ---
    "left_on_read_react_chance": 0.50,
    "left_on_read_ignore_chance": 0.20,
    "late_reply_chance": 0.12,
    "late_reply_min_delay": 5.0,
    "late_reply_max_delay": 30.0,
    "typing_hesitation_chance": 0.15,
    "typo_chance_normal": 0.05,
    "typo_chance_drunk": 0.25,
    "message_edit_chance": 0.04,
    "message_delete_chance_normal": 0.015,
    "message_delete_chance_drunk": 0.10,
    "screenshot_paranoia_chance": 0.04,
    "eavesdrop_chance": 0.05,
    "status_roast_chance": 0.15,

    # --- Background Tasks ---
    "unprompted_enabled": True,
    "unprompted_min_interval": 1800,
    "unprompted_max_interval": 3600,
    "unprompted_dead_threshold": 2700,
    "unprompted_chance": 0.25,
    "wrong_chat_enabled": True,
    "wrong_chat_min_interval": 7200,
    "wrong_chat_max_interval": 18000,
    "wrong_chat_chance": 0.15,
    "story_enabled": True,
    "story_min_interval": 43200,
    "story_max_interval": 86400,
    "status_cycling_enabled": True,

    # --- Channel IDs ---
    "target_channel_id": 1492604782874067075,
    "story_channel_id": 1346667584669487224,
    "nsfw_channel_id": "1495092765942612159",
    "allowed_dm_user_id": 1276870533811540031,

    # --- Role IDs ---
    "hinglish_role_id": 1263157325653479477,
    "male_role_id": 916228722678456320,
    "female_role_id": 916228772762619974,
    "lewd_allowed_role_id": 916228546664464396,

    # --- AI Configuration ---
    "temperature": 0.9,
    "model": "gemma-4-31b-it",
    "mood_duration_hours": 6,
    "memory_compress_threshold": 20,
    "memory_keep_count": 10,
    "return_detection_days": 3,

    # --- Mood Pool ---
    "mood_pool": ["NORMAL", "NORMAL", "YAPPING", "ANNOYED", "LEWD", "BORED"],

    # --- Lists ---
    "dry_texts": [
        "ok", "okay", "k", "kk", "lol", "lmao", "haha", "hah", "ha", "hmm",
        "oh", "ah", "mhm", "yep", "yea", "yeah", "nah", "nope", "sure",
        "cool", "nice", "true", "fr", "bet", "ight", "aight", "ye", "ya",
        "ig", "ik", "idk", "ic", "ooh", "oof", "rip", "f", "bruh", "damn",
        "wow", "ikr", "smh", "tbh", "ngl", "wdym", "ohh", "ohhh",
        "hm", "hmmm", "mmm", "mm", "meh"
    ],
    "left_on_read_reactions": ["👁️", "✅", "👀", "💀", "🫥"],
    "wrong_chat_messages": [
        "yeah grab the spicy ones",
        "wait he said WHAT",
        "no i think the blue one is cuter",
        "omg i just saw her story 💀",
        "bro that's literally not how you make maggi",
        "can you send me that playlist again",
        "i think my cat ate something weird",
        "tell her i said hi but like casually",
        "wait which app is cheaper for delivery rn",
        "no literally he's so annoying i can't",
        "the pink hoodie or the black one??",
        "i'm not going if she's going"
    ],
    "fallback_messages": [
        "my wifi is acting up...",
        "ignoring you rn.",
        "brb my phone is dying.",
        "discord is glitching or smth... talk later.",
        "idk what's happening but something broke."
    ],

    # --- Status Schedule (IST hour -> [activity_type, activity_name]) ---
    "status_schedule": {
        "6": ["listening", "alarm going off"],
        "7": ["custom", "☕"],
        "8": ["listening", "Spotify"],
        "9": ["watching", "reels"],
        "10": ["playing", "doing nothing productive"],
        "11": ["listening", "Spotify"],
        "12": ["custom", "hungry."],
        "13": ["custom", "eating"],
        "14": ["watching", "youtube"],
        "15": ["playing", "Valorant"],
        "16": ["playing", "Valorant"],
        "17": ["listening", "Spotify"],
        "18": ["custom", "🌙"],
        "19": ["watching", "anime"],
        "20": ["watching", "anime"],
        "21": ["playing", "Valorant"],
        "22": ["listening", "Spotify"],
        "23": ["custom", "can't sleep"],
        "0": ["custom", "💤"],
        "1": ["custom", "💤"],
    },
}

# Track bot start time
import time
start_time = time.time()


def get(key, default=None):
    """Thread-safe config read."""
    with _lock:
        return config.get(key, default)


def set(key, value):
    """Thread-safe config write."""
    with _lock:
        config[key] = value


def get_all():
    """Thread-safe full config read."""
    with _lock:
        return dict(config)


def update(updates: dict):
    """Thread-safe bulk config update."""
    with _lock:
        for k, v in updates.items():
            if k in config:
                # Type coerce to match existing type
                existing = config[k]
                if isinstance(existing, bool) and not isinstance(v, bool):
                    config[k] = str(v).lower() in ("true", "1", "yes")
                elif isinstance(existing, int) and not isinstance(v, bool):
                    config[k] = int(v)
                elif isinstance(existing, float):
                    config[k] = float(v)
                else:
                    config[k] = v
