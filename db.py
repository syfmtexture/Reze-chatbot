import os
import motor.motor_asyncio
import certifi
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import logging

load_dotenv()
logger = logging.getLogger('db')

MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    logger.warning("MONGODB_URI not found in .env")

# Initialize Motor Client with explicit TLS certificates
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client['reze_bot']
channels_col = db['channels']
users_col = db['users']
server_configs_col = db['server_configs']


# --- SERVER CONFIG (per-guild settings) ---

async def get_server_config(guild_id: str) -> dict:
    """Get server-specific config. Returns empty dict if not configured."""
    doc = await server_configs_col.find_one({"_id": guild_id})
    return doc or {}

async def set_server_config(guild_id: str, key: str, value):
    """Set a single config key for a server."""
    await server_configs_col.update_one(
        {"_id": guild_id},
        {"$set": {key: value}},
        upsert=True
    )

async def get_all_server_configs() -> list:
    """Get all server configs (for dashboard)."""
    return await server_configs_col.find().to_list(length=100)

async def get_channel_memory(channel_id: str) -> dict:
    """Fetches the channel's memory, including the summary and recent messages."""
    doc = await channels_col.find_one({"_id": channel_id})
    if not doc:
        return {"summary": "", "messages": []}
    return {
        "summary": doc.get("summary", ""),
        "messages": doc.get("messages", [])
    }

async def add_message(channel_id: str, role: str, content: str):
    """Appends a new message to the channel's memory."""
    await channels_col.update_one(
        {"_id": channel_id},
        {"$push": {"messages": {"role": role, "content": content}}},
        upsert=True
    )

async def update_summary_and_trim(channel_id: str, new_summary: str, keep_messages: list):
    """Updates the long-term summary and trims the message array to keep context small."""
    await channels_col.update_one(
        {"_id": channel_id},
        {"$set": {
            "summary": new_summary,
            "messages": keep_messages
        }},
        upsert=True
    )

# --- USER RELATIONSHIP TRACKING ---

async def get_user_data(user_id: str) -> dict:
    """Fetches a user's relationship data. Returns None if user not found."""
    return await users_col.find_one({"_id": user_id})

async def update_user_interaction(user_id: str, display_name: str, server_name: str = None, channel_name: str = None) -> dict:
    """Called on every interaction. Returns PREVIOUS user data (for absence detection), then updates.
    Now also tracks which servers/channels the user has talked to Reze in."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    existing = await users_col.find_one({"_id": user_id})

    # Build interaction location info
    location_entry = None
    if server_name and channel_name:
        location_entry = f"{server_name}/#{channel_name}"
    elif channel_name:
        location_entry = f"DM"

    if not existing:
        new_doc = {
            "_id": user_id,
            "display_name": display_name,
            "first_seen": now,
            "last_seen": now,
            "last_interaction_date": today,
            "total_messages": 1,
            "streak_days": 1,
            "closeness": 0.0,
            "notes": "",
            "user_memory": "",
            "recent_servers": [location_entry] if location_entry else [],
            "last_server": location_entry or ""
        }
        await users_col.insert_one(new_doc)
        return None  # First time — no previous data

    last_date = existing.get("last_interaction_date", "")
    streak = existing.get("streak_days", 0)
    closeness = existing.get("closeness", 0.0)

    update_set = {"last_seen": now, "display_name": display_name}
    if location_entry:
        update_set["last_server"] = location_entry

    if last_date == today:
        update_ops = {"$set": update_set, "$inc": {"total_messages": 1}}
    else:
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        streak = streak + 1 if last_date == yesterday else 1
        closeness = min(closeness + 0.5, 10.0)
        update_set.update({
            "last_interaction_date": today,
            "streak_days": streak,
            "closeness": closeness
        })
        update_ops = {"$set": update_set, "$inc": {"total_messages": 1}}

    # Track recent servers (keep last 10 unique locations)
    if location_entry:
        recent = existing.get("recent_servers", [])
        if location_entry not in recent:
            recent.append(location_entry)
            recent = recent[-10:]  # Keep last 10 unique
        update_ops.setdefault("$set", {})["recent_servers"] = recent

    await users_col.update_one({"_id": user_id}, update_ops)
    return existing  # Previous data for absence detection

async def update_user_notes(user_id: str, notes: str):
    """Update the AI-generated relationship notes for a user."""
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"notes": notes}},
        upsert=True
    )

async def get_user_memory(user_id: str) -> str:
    """Get the user-level cross-server memory summary."""
    doc = await users_col.find_one({"_id": user_id}, {"user_memory": 1})
    if doc:
        return doc.get("user_memory", "")
    return ""

async def update_user_memory(user_id: str, memory: str):
    """Update the user-level cross-server memory summary."""
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"user_memory": memory}},
        upsert=True
    )


# --- WEB IMAGE TRACKING ---

async def is_image_sent(channel_id: str, url: str) -> bool:
    """Checks if an image URL has already been sent in this channel."""
    doc = await db['sent_images'].find_one({"channel_id": channel_id, "url": url})
    return doc is not None


async def record_sent_image(channel_id: str, url: str):
    """Records a sent image URL in MongoDB to prevent future repetitions."""
    await db['sent_images'].update_one(
        {"channel_id": channel_id, "url": url},
        {"$set": {"sent_at": datetime.now(timezone.utc)}},
        upsert=True
    )
