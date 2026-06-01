"""
Reze Bot Dashboard — Flask API Backend
Provides endpoints for the web dashboard to control the bot.
"""

from flask import Blueprint, request, jsonify, session
import pymongo
import certifi
import os
import time
from datetime import datetime, timezone
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

dashboard_bp = Blueprint('dashboard', __name__)

# --- Bot references (set by main.py on startup) ---
_bot = None
_ai = None
_grudge_list = None
_channel_last_activity = None
_unprompted_waiting = None
_user_msg_timestamps = None

# --- Sync MongoDB client for dashboard ---
_mongo_db = None


def init_bot_refs(bot, ai, grudge_list, channel_last_activity, unprompted_waiting, user_msg_timestamps):
    """Called by main.py to pass live bot references to the dashboard."""
    global _bot, _ai, _grudge_list, _channel_last_activity, _unprompted_waiting, _user_msg_timestamps, _mongo_db
    _bot = bot
    _ai = ai
    _grudge_list = grudge_list
    _channel_last_activity = channel_last_activity
    _unprompted_waiting = unprompted_waiting
    _user_msg_timestamps = user_msg_timestamps

    uri = os.getenv("MONGODB_URI")
    if uri:
        client = pymongo.MongoClient(uri, tlsCAFile=certifi.where())
        _mongo_db = client['reze_bot']


# --- Auth Decorator ---
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# --- Root API Route ---
@dashboard_bp.route('/')
def api_root():
    return jsonify({"status": "active", "message": "Makima Chatbot API is running"})


# --- Auth Routes ---
@dashboard_bp.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    password = data.get('password', '')
    expected = os.getenv('DASHBOARD_PASSWORD')
    if not expected:
        return jsonify({"error": "dashboard password not configured"}), 500
    if password == expected:
        session['authenticated'] = True
        return jsonify({"success": True})
    return jsonify({"error": "wrong password"}), 401


@dashboard_bp.route('/api/logout', methods=['POST'])
def logout():
    session.pop('authenticated', None)
    return jsonify({"success": True})


@dashboard_bp.route('/api/auth-check')
def auth_check():
    return jsonify({"authenticated": session.get('authenticated', False)})


# --- Status ---
@dashboard_bp.route('/api/status')
@require_auth
def get_status():
    import bot_config
    uptime = int(time.time() - bot_config.start_time)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)

    bot_name = "Unknown"
    bot_id = "Unknown"
    guild_count = 0
    is_ready = False
    if _bot:
        is_ready = _bot.is_ready()
        if _bot.user:
            bot_name = _bot.user.name
            bot_id = str(_bot.user.id)
        guild_count = len(_bot.guilds) if _bot.guilds else 0

    model = bot_config.get("model", "unknown")
    key_count = len(_ai.api_keys) if _ai else 0
    current_key = (_ai.current_key_index + 1) if _ai else 0

    return jsonify({
        "bot_name": bot_name,
        "bot_id": bot_id,
        "is_ready": is_ready,
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime,
        "guild_count": guild_count,
        "model": model,
        "api_key_count": key_count,
        "current_api_key": current_key,
    })


# --- Config ---
@dashboard_bp.route('/api/config')
@require_auth
def get_config():
    import bot_config
    return jsonify(bot_config.get_all())


@dashboard_bp.route('/api/config', methods=['POST'])
@require_auth
def update_config():
    import bot_config
    data = request.get_json()
    bot_config.update(data)
    # Also push relevant values to the ai handler
    if _ai:
        _ai.model = bot_config.get("model")
    return jsonify({"success": True})


# --- Personality ---
@dashboard_bp.route('/api/personality')
@require_auth
def get_personality():
    if _ai:
        return jsonify({"prompt": _ai._get_base_prompt()})
    return jsonify({"prompt": ""})


@dashboard_bp.route('/api/personality', methods=['POST'])
@require_auth
def update_personality():
    data = request.get_json()
    new_prompt = data.get('prompt', '')
    if _ai and new_prompt:
        _ai._custom_prompt = new_prompt
    return jsonify({"success": True})


# --- Moods ---
@dashboard_bp.route('/api/moods')
@require_auth
def get_moods():
    moods = {}
    if _ai:
        for channel_id, state in _ai.channel_state.items():
            moods[channel_id] = {
                "mood": state.get("mood", "NORMAL"),
                "mood_expiry": state.get("mood_expiry", 0),
                "nsfw_toggle": state.get("nsfw_toggle", False),
                "image_cooldown": state.get("image_cooldown", 0),
            }
    return jsonify(moods)


@dashboard_bp.route('/api/moods/force', methods=['POST'])
@require_auth
def force_mood():
    data = request.get_json()
    channel_id = data.get('channel_id')
    mood = data.get('mood', 'NORMAL')
    if _ai and channel_id:
        if channel_id not in _ai.channel_state:
            _ai.channel_state[channel_id] = {}
        _ai.channel_state[channel_id]["mood"] = mood
        _ai.channel_state[channel_id]["mood_expiry"] = time.time() + 3600
    return jsonify({"success": True})


# --- Users ---
@dashboard_bp.route('/api/users')
@require_auth
def get_users():
    if not _mongo_db:
        return jsonify([])
    users = list(_mongo_db['users'].find().sort("total_messages", -1))
    for u in users:
        u['_id'] = str(u['_id'])
        if 'first_seen' in u and isinstance(u['first_seen'], datetime):
            u['first_seen'] = u['first_seen'].isoformat()
        if 'last_seen' in u and isinstance(u['last_seen'], datetime):
            u['last_seen'] = u['last_seen'].isoformat()
    return jsonify(users)


@dashboard_bp.route('/api/users/<user_id>/notes', methods=['POST'])
@require_auth
def update_user_notes(user_id):
    if not _mongo_db:
        return jsonify({"error": "no db"}), 500
    data = request.get_json()
    notes = data.get('notes', '')
    _mongo_db['users'].update_one({"_id": user_id}, {"$set": {"notes": notes}})
    return jsonify({"success": True})


@dashboard_bp.route('/api/users/<user_id>/closeness', methods=['POST'])
@require_auth
def update_user_closeness(user_id):
    if not _mongo_db:
        return jsonify({"error": "no db"}), 500
    data = request.get_json()
    closeness = float(data.get('closeness', 0))
    _mongo_db['users'].update_one({"_id": user_id}, {"$set": {"closeness": min(max(closeness, 0), 10)}})
    return jsonify({"success": True})


# --- Memory ---
@dashboard_bp.route('/api/memory')
@require_auth
def list_channels():
    if not _mongo_db:
        return jsonify([])
    channels = list(_mongo_db['channels'].find({}, {"_id": 1, "summary": 1, "messages": {"$slice": -1}}))
    result = []
    for ch in channels:
        result.append({
            "channel_id": ch['_id'],
            "has_summary": bool(ch.get('summary')),
            "message_count": _mongo_db['channels'].find_one({"_id": ch['_id']}, {"messages": 1}).get('messages', []),
        })
    # Simplify message_count
    for r in result:
        r['message_count'] = len(r['message_count']) if isinstance(r['message_count'], list) else 0
    return jsonify(result)


@dashboard_bp.route('/api/memory/<path:channel_id>')
@require_auth
def get_memory(channel_id):
    if not _mongo_db:
        return jsonify({"summary": "", "messages": []})
    doc = _mongo_db['channels'].find_one({"_id": channel_id})
    if not doc:
        return jsonify({"summary": "", "messages": []})
    return jsonify({
        "summary": doc.get("summary", ""),
        "messages": doc.get("messages", [])[-50:]  # Last 50 messages
    })


@dashboard_bp.route('/api/memory/<path:channel_id>', methods=['DELETE'])
@require_auth
def wipe_memory(channel_id):
    if not _mongo_db:
        return jsonify({"error": "no db"}), 500
    _mongo_db['channels'].delete_one({"_id": channel_id})
    return jsonify({"success": True})


@dashboard_bp.route('/api/memory/<path:channel_id>/summary', methods=['POST'])
@require_auth
def update_summary(channel_id):
    if not _mongo_db:
        return jsonify({"error": "no db"}), 500
    data = request.get_json()
    summary = data.get('summary', '')
    _mongo_db['channels'].update_one({"_id": channel_id}, {"$set": {"summary": summary}}, upsert=True)
    return jsonify({"success": True})


# --- Grudges ---
@dashboard_bp.route('/api/grudges')
@require_auth
def get_grudges():
    if not _grudge_list:
        return jsonify({})
    now = time.time()
    result = {}
    for uid, expiry in _grudge_list.items():
        result[str(uid)] = {
            "expires_in": max(0, int(expiry - now)),
            "expired": now >= expiry,
        }
    return jsonify(result)


@dashboard_bp.route('/api/grudges/<user_id>', methods=['DELETE'])
@require_auth
def clear_grudge(user_id):
    if _grudge_list:
        uid = int(user_id)
        if uid in _grudge_list:
            del _grudge_list[uid]
    return jsonify({"success": True})


# --- Tasks ---
@dashboard_bp.route('/api/tasks')
@require_auth
def get_tasks():
    import bot_config
    return jsonify({
        "unprompted": bot_config.get("unprompted_enabled"),
        "wrong_chat": bot_config.get("wrong_chat_enabled"),
        "story": bot_config.get("story_enabled"),
        "status_cycling": bot_config.get("status_cycling_enabled"),
        "eavesdrop": bot_config.get("eavesdrop_enabled"),
    })


@dashboard_bp.route('/api/tasks', methods=['POST'])
@require_auth
def toggle_tasks():
    import bot_config
    data = request.get_json()
    mapping = {
        "unprompted": "unprompted_enabled",
        "wrong_chat": "wrong_chat_enabled",
        "story": "story_enabled",
        "status_cycling": "status_cycling_enabled",
        "eavesdrop": "eavesdrop_enabled",
    }
    for key, config_key in mapping.items():
        if key in data:
            bot_config.set(config_key, bool(data[key]))
    return jsonify({"success": True})


# --- Memes ---
@dashboard_bp.route('/api/memes')
@require_auth
def list_memes():
    meme_dir = os.path.join(os.path.dirname(__file__), 'assets', 'memes')
    if not os.path.exists(meme_dir):
        return jsonify([])
    files = []
    for f in os.listdir(meme_dir):
        fpath = os.path.join(meme_dir, f)
        if os.path.isfile(fpath):
            files.append({
                "name": f,
                "size": os.path.getsize(fpath),
            })
    return jsonify(files)
