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

async def update_user_interaction(user_id: str, display_name: str) -> dict:
    """Called on every interaction. Returns PREVIOUS user data (for absence detection), then updates."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    existing = await users_col.find_one({"_id": user_id})

    if not existing:
        await users_col.insert_one({
            "_id": user_id,
            "display_name": display_name,
            "first_seen": now,
            "last_seen": now,
            "last_interaction_date": today,
            "total_messages": 1,
            "streak_days": 1,
            "closeness": 0.0,
            "notes": ""
        })
        return None  # First time — no previous data

    last_date = existing.get("last_interaction_date", "")
    streak = existing.get("streak_days", 0)
    closeness = existing.get("closeness", 0.0)

    if last_date == today:
        await users_col.update_one(
            {"_id": user_id},
            {"$set": {"last_seen": now, "display_name": display_name},
             "$inc": {"total_messages": 1}}
        )
    else:
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        streak = streak + 1 if last_date == yesterday else 1
        closeness = min(closeness + 0.5, 10.0)

        await users_col.update_one(
            {"_id": user_id},
            {"$set": {
                "last_seen": now,
                "last_interaction_date": today,
                "display_name": display_name,
                "streak_days": streak,
                "closeness": closeness
            }, "$inc": {"total_messages": 1}}
        )

    return existing  # Previous data for absence detection

async def update_user_notes(user_id: str, notes: str):
    """Update the AI-generated relationship notes for a user."""
    await users_col.update_one(
        {"_id": user_id},
        {"$set": {"notes": notes}},
        upsert=True
    )
