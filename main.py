import os
import sys
import discord
from dotenv import load_dotenv
from ai_handler import AIHandler
import logging
import asyncio

# Ensure unicode output works correctly on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

import time
import random
import glob
import re
import aiohttp
import io
import urllib.parse
from datetime import timedelta, datetime, timezone
from keep_alive import keep_alive
import db
import bot_config
from PIL import Image

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

# Initialize AI Handler
ai = AIHandler()

# Hardcoded defaults (your original server)
DEFAULT_HINGLISH_ROLE_ID = 1263157325653479477
DEFAULT_MALE_ROLE_ID = 916228722678456320
DEFAULT_FEMALE_ROLE_ID = 916228772762619974
DEFAULT_LEWD_ROLE_ID = 916228546664464396
DEFAULT_TARGET_CHANNEL_ID = 1492604782874067075
DEFAULT_STORY_CHANNEL_ID = 1346667584669487224
DEFAULT_NSFW_CHANNEL_ID = "1495092765942612159"

# In-memory cache for server configs (guild_id -> config dict)
_server_config_cache = {}

async def get_guild_config(guild_id: int) -> dict:
    """Get server config with in-memory cache. Falls back to hardcoded defaults."""
    gid = str(guild_id)
    if gid not in _server_config_cache:
        _server_config_cache[gid] = await db.get_server_config(gid)
    return _server_config_cache[gid]

def get_role_id(config: dict, key: str, default: int) -> int:
    """Get a role ID from server config, falling back to hardcoded default."""
    return config.get(key, default)

def get_channel_id(config: dict, key: str, default) -> int:
    """Get a channel ID from server config, falling back to hardcoded default."""
    val = config.get(key, default)
    return int(val) if val else int(default)


def translate_tags(query: str, is_booru: bool) -> str:
    """
    Translates a user/AI search query into proper search format.
    - If is_booru is True, it converts terms to lower case and ensures 'reze_(chainsaw_man)' is used.
    - If is_booru is False (e.g. Reddit), it keeps it normal: 'reze <query>'.
    """
    cleaned = query.lower().strip()
    # Remove weird punctuation that could break tags (excluding parenthesis/underscores for tags like reze_(chainsaw_man))
    cleaned = re.sub(r'[^\w\s\(\)_]', '', cleaned)
    
    if is_booru:
        if "reze_(chainsaw_man)" not in cleaned and "reze" in cleaned:
            cleaned = cleaned.replace("reze", "reze_(chainsaw_man)")
        elif "reze" not in cleaned:
            cleaned = f"reze_(chainsaw_man) {cleaned}"
            
        tags = [t.strip() for t in cleaned.split() if t.strip()]
        return " ".join(tags)
    else:
        if "reze" not in cleaned:
            cleaned = f"reze {cleaned}"
        return cleaned


# Creator Discord IDs (all alts of the same person)
CREATOR_DISCORD_IDS = {1276870533811540031}  # Add all creator Discord user IDs here
CREATOR_USERNAMES = {"syfmyorii", "realyorii", "issgrid", "nottkai", "spikiee"}

# Global event cooldown to prevent join/leave/unprompted flooding
last_event_message_time = 0
EVENT_COOLDOWN_SECONDS = 300  # 5 minutes between any event-driven messages

# ========================
# SLASH COMMANDS
# ========================

@tree.command(name="setup", description="Show current server config for Reze")
@discord.app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    config = await get_guild_config(interaction.guild_id)
    embed = discord.Embed(title="Reze Server Config", color=0x9B59B6)
    embed.add_field(name="Male Role", value=f"<@&{config['male_role_id']}>" if config.get('male_role_id') else "Not set (using default)", inline=True)
    embed.add_field(name="Female Role", value=f"<@&{config['female_role_id']}>" if config.get('female_role_id') else "Not set (using default)", inline=True)
    embed.add_field(name="Hinglish Role", value=f"<@&{config['hinglish_role_id']}>" if config.get('hinglish_role_id') else "Not set (using default)", inline=True)
    embed.add_field(name="Lewd Role", value=f"<@&{config['lewd_role_id']}>" if config.get('lewd_role_id') else "Not set (using default)", inline=True)
    embed.add_field(name="Target Channel", value=f"<#{config['target_channel_id']}>" if config.get('target_channel_id') else "Not set (using default)", inline=True)
    embed.add_field(name="NSFW Channel", value=f"<#{config['nsfw_channel_id']}>" if config.get('nsfw_channel_id') else "Not set (using default)", inline=True)
    embed.set_footer(text="Use /setrole and /setchannel to configure")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="setrole", description="Set a role for Reze to recognize in this server")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(
    role_type="Which role to set",
    role="The role to assign"
)
@discord.app_commands.choices(role_type=[
    discord.app_commands.Choice(name="Male", value="male_role_id"),
    discord.app_commands.Choice(name="Female", value="female_role_id"),
    discord.app_commands.Choice(name="Hinglish", value="hinglish_role_id"),
    discord.app_commands.Choice(name="Lewd Allowed", value="lewd_role_id"),
])
async def slash_setrole(interaction: discord.Interaction, role_type: discord.app_commands.Choice[str], role: discord.Role):
    gid = str(interaction.guild_id)
    await db.set_server_config(gid, role_type.value, role.id)
    _server_config_cache.pop(gid, None)  # Invalidate cache
    await interaction.response.send_message(f"done. **{role_type.name}** role set to {role.mention}", ephemeral=True)

@tree.command(name="setchannel", description="Set a channel for Reze in this server")
@discord.app_commands.default_permissions(administrator=True)
@discord.app_commands.describe(
    channel_type="Which channel to set",
    channel="The channel to assign"
)
@discord.app_commands.choices(channel_type=[
    discord.app_commands.Choice(name="Target (main hangout)", value="target_channel_id"),
    discord.app_commands.Choice(name="NSFW", value="nsfw_channel_id"),
    discord.app_commands.Choice(name="Story", value="story_channel_id"),
])
async def slash_setchannel(interaction: discord.Interaction, channel_type: discord.app_commands.Choice[str], channel: discord.TextChannel):
    gid = str(interaction.guild_id)
    await db.set_server_config(gid, channel_type.value, channel.id)
    _server_config_cache.pop(gid, None)  # Invalidate cache
    await interaction.response.send_message(f"done. **{channel_type.name}** channel set to {channel.mention}", ephemeral=True)

@tree.command(name="resetconfig", description="Reset all Reze config for this server to defaults")
@discord.app_commands.default_permissions(administrator=True)
async def slash_resetconfig(interaction: discord.Interaction):
    gid = str(interaction.guild_id)
    await db.server_configs_col.delete_one({"_id": gid})
    _server_config_cache.pop(gid, None)
    await interaction.response.send_message("config reset to defaults.", ephemeral=True)

# --- NEW: Rate Limiting & Fallbacks ---
user_msg_timestamps = {}

FALLBACK_MESSAGES = [
    "my wifi is acting up...",
    "ignoring you rn.",
    "brb my phone is dying.",
    "discord is glitching or smth... talk later.",
    "idk what's happening but something broke."
]

# --- NEW: Strict MIME Types ---
# We block weird formats like .mp4, PDFs, or raw binaries that would crash the API
ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"]

# --- HUMAN BEHAVIOR SYSTEMS ---
# Grudge list: users Reze is temporarily ignoring (user_id -> expiry timestamp)
grudge_list = {}

# Per-channel async locks to prevent message interleaving
channel_locks = {}

# Track last message time per channel (for unprompted messages)
channel_last_activity = {}

# Track channels currently undergoing memory compression to prevent concurrent API storms
active_compressions = set()

# Dry text detection (messages that deserve to be left on read)
DRY_TEXTS = {
    "ok", "okay", "k", "kk", "lol", "lmao", "haha", "hah", "ha", "hmm",
    "oh", "ah", "mhm", "yep", "yea", "yeah", "nah", "nope", "sure",
    "cool", "nice", "true", "fr", "bet", "ight", "aight", "ye", "ya",
    "ig", "ik", "idk", "ic", "ooh", "oof", "rip", "f", "bruh", "damn",
    "wow", "ikr", "smh", "tbh", "ngl", "wdym", "ohh", "ohhh",
    "hm", "hmmm", "mmm", "mm", "meh"
}

# Left-on-Read reactions (what she does instead of replying)
LEFT_ON_READ_REACTIONS = ["👁️", "✅", "👀", "💀", "🫥"]

# Wrong chat messages (out-of-context snippets)
WRONG_CHAT_MESSAGES = [
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
]

# AFK simulation tracker (channel_id -> True if she's "away")
afk_until = {}  # channel_id -> timestamp when she comes back

# Discord Rich Presence schedules (IST hour -> activity)
STATUS_SCHEDULE = {
    6: (discord.ActivityType.listening, "alarm going off"),
    7: (discord.ActivityType.custom, "☕"),
    8: (discord.ActivityType.listening, "Spotify"),
    9: (discord.ActivityType.watching, "reels"),
    10: (discord.ActivityType.playing, "doing nothing productive"),
    11: (discord.ActivityType.listening, "Spotify"),
    12: (discord.ActivityType.custom, "hungry."),
    13: (discord.ActivityType.custom, "eating"),
    14: (discord.ActivityType.watching, "youtube"),
    15: (discord.ActivityType.playing, "Valorant"),
    16: (discord.ActivityType.playing, "Valorant"),
    17: (discord.ActivityType.listening, "Spotify"),
    18: (discord.ActivityType.custom, "🌙"),
    19: (discord.ActivityType.watching, "anime"),
    20: (discord.ActivityType.watching, "anime"),
    21: (discord.ActivityType.playing, "Valorant"),
    22: (discord.ActivityType.listening, "Spotify"),
    23: (discord.ActivityType.custom, "can't sleep"),
    0: (discord.ActivityType.custom, "💤"),
    1: (discord.ActivityType.custom, "💤"),
}

# Message edit phrases (what she "fixes" after sending)
EDIT_SWAPS = [
    ("i", "I"),  # fixes capitalization
    ("dont", "don't"),
    ("cant", "can't"),
    ("wont", "won't"),
    ("im", "i'm"),
]

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("Bot is ready. Mention me or reply to my message to chat.")
    print("------")
    # Sync slash commands
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    # Initialize dashboard with bot references
    from dashboard import init_bot_refs
    init_bot_refs(bot, ai, grudge_list, channel_last_activity, unprompted_waiting_for_reply, user_msg_timestamps)
    print("Dashboard initialized with bot references.")
    
    # Load mirrored state if active
    try:
        state = await db.get_mirror_state()
        if state and state.get("active"):
            ai.mirror_active = True
            ai.mirror_target_id = state.get("target_user_id")
            ai.mirror_target_name = state.get("target_name")
            ai.mirror_profile = state.get("profile")
            print(f"Loaded active mirror state: mirroring user {ai.mirror_target_name} ({ai.mirror_target_id})")
    except Exception as e:
        print(f"Failed to load mirror state on startup: {e}")

    # Start background tasks
    bot.loop.create_task(unprompted_message_loop())
    bot.loop.create_task(wrong_chat_loop())
    bot.loop.create_task(status_cycling_loop())
    bot.loop.create_task(story_posting_loop())

async def execute_mirror(message, target_member):
    try:
        await message.channel.send(f"fine. let me stalk {target_member.display_name} for a second...")
        
        # Gather up to 300 messages from the target user
        target_messages = []
        async for msg in message.channel.history(limit=1000):
            if msg.author.id == target_member.id and msg.content:
                content = msg.content.strip()
                if not (content.startswith("?") or bot.user in msg.mentions):
                    target_messages.append(content)
                    if len(target_messages) >= 300:
                        break
        
        # If we got fewer than 100 messages, fall back to the MongoDB recent messages list
        if len(target_messages) < 100:
            db_messages = await db.get_user_recent_messages(str(target_member.id))
            for m in db_messages:
                if m not in target_messages:
                    target_messages.append(m)
                    if len(target_messages) >= 300:
                        break
                        
        if not target_messages:
            await message.reply("i couldn't find any recent messages from them... are they a ghost or smth?")
            return
            
        await message.channel.send("running linguistic analysis on their style...")
        profile = await ai.analyze_user_personality(target_member.display_name, target_messages)
        
        # Persist the state in DB and cache
        await db.set_mirror_state(str(target_member.id), target_member.display_name, profile)
        ai.mirror_active = True
        ai.mirror_target_id = str(target_member.id)
        ai.mirror_target_name = target_member.display_name
        ai.mirror_profile = profile
        
        # Apply guild nickname
        if message.guild:
            try:
                await message.guild.me.edit(nick=target_member.display_name)
            except Exception as nick_err:
                print(f"Failed to change guild nickname: {nick_err}")

        # Clear presence activity during mirroring
        try:
            await bot.change_presence(activity=None)
        except Exception as pres_err:
            print(f"Failed to clear presence activity: {pres_err}")
            
        await message.channel.send("done. i've updated my server nickname and personality!")
    except Exception as e:
        logger.error(f"Error executing mirror command: {e}")
        await message.channel.send("something broke while trying to mirror them 💀")

async def execute_unmirror(message):
    try:
        await message.channel.send("fine... unmirroring. giving you your normal bot back.")
        
        # Revert guild nickname
        if message.guild:
            try:
                await message.guild.me.edit(nick=None)
            except Exception as nick_err:
                print(f"Failed to reset guild nickname: {nick_err}")
            
        # Clear DB and cache
        await db.clear_mirror_state()
        ai.mirror_active = False
        ai.mirror_target_id = None
        ai.mirror_target_name = None
        ai.mirror_profile = ""

        # Reset presence status
        try:
            await bot.change_presence(status=discord.Status.online, activity=None)
        except Exception as pres_err:
            print(f"Failed to reset presence on unmirror: {pres_err}")
        
        await message.channel.send("thank god, being someone else was exhausting.")
    except Exception as e:
        logger.error(f"Error executing unmirror command: {e}")
        await message.channel.send("failed to unmirror properly 💀 try again later.")

@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    clean_content = message.content.strip()
    
    # Check for prefix commands (mirror / unmirror)
    if clean_content.startswith("?mirror") or clean_content.startswith("?unmirror"):
        if message.author.id != 1276870533811540031:
            try:
                await message.reply("you don't have permission to tell me what to do lol.")
            except:
                pass
            return
            
        if clean_content.startswith("?mirror"):
            parts = clean_content.split(None, 1)
            cmd_arg = parts[1].strip() if len(parts) > 1 else ""
            
            if cmd_arg.lower() in ["reset", "stop"]:
                await execute_unmirror(message)
                return
                
            target_member = None
            for mention in message.mentions:
                if mention.id != bot.user.id:
                    target_member = mention
                    break
            
            if not target_member:
                try:
                    await message.reply("you need to tag someone to mirror them, dummy.")
                except:
                    pass
                return
                
            await execute_mirror(message, target_member)
            return
            
        elif clean_content.startswith("?unmirror"):
            await execute_unmirror(message)
            return

    is_dm = isinstance(message.channel, discord.DMChannel)
    ALLOWED_DM_USER_ID = 1276870533811540031

    if is_dm:
        if message.author.id != ALLOWED_DM_USER_ID:
            return
            
        channel_id = f"dm_{message.author.id}"
        
        # Toggle NSFW command
        if message.content.strip().lower() == "/nsfw":
            if channel_id not in ai.channel_state:
                ai.channel_state[channel_id] = {"slangs": [], "emojis": [], "mood": "NORMAL", "mood_expiry": 0}
            
            current_state = ai.channel_state[channel_id].get("nsfw_toggle", False)
            ai.channel_state[channel_id]["nsfw_toggle"] = not current_state
            
            if not current_state:
                # Turning ON — reset phase counter so it starts from teasing
                ai.channel_state[channel_id]["nsfw_msg_count"] = 0
                on_responses = ["hmm okay~", "fine. don't make it weird.", "👀", "oh? ok then.", "sure, if you can handle it"]
                await message.reply(random.choice(on_responses))
            else:
                # Turning OFF — reset counter for next time
                ai.channel_state[channel_id]["nsfw_msg_count"] = 0
                off_responses = ["back to normal i guess", "okay putting my clothes back on metaphorically", "finally", "k", "that was... interesting"]
                await message.reply(random.choice(off_responses))
            return
            
    else:
        channel_id = str(message.channel.id)
        
        # Determine if the bot should respond in server
        is_mentioned = bot.user in message.mentions
        is_reply_to_bot = (
            message.reference and 
            message.reference.resolved and 
            isinstance(message.reference.resolved, discord.Message) and 
            message.reference.resolved.author == bot.user
        )

        # Eavesdropping Logic — use per-server target channel
        guild_config = await get_guild_config(message.guild.id) if message.guild else {}
        target_ch_id = get_channel_id(guild_config, 'target_channel_id', DEFAULT_TARGET_CHANNEL_ID)
        will_eavesdrop = False
        
        if not (is_mentioned or is_reply_to_bot):
            if message.channel.id == target_ch_id:
                msg_lower = message.content.lower()
                trigger_name = ai.mirror_target_name.lower() if (ai.mirror_active and ai.mirror_target_name) else "reze"
                if trigger_name in msg_lower:
                    will_eavesdrop = True
                elif random.random() < 0.05: # 5% random chance
                    will_eavesdrop = True
                    
            if not will_eavesdrop:
                return

    # --- NEW: Rate Limiting Enforcement (Anti-Spam) ---
    user_id = message.author.id
    current_time = time.time()
    
    if user_id not in user_msg_timestamps:
        user_msg_timestamps[user_id] = []
        
    # Clean old timestamps
    user_msg_timestamps[user_id] = [t for t in user_msg_timestamps[user_id] if current_time - t < bot_config.get('rate_limit_window', 40)]
    
    if len(user_msg_timestamps[user_id]) >= bot_config.get('rate_limit_count', 5):
        await message.reply("you're spamming me. slow down or i'm ignoring you.", delete_after=5)
        return
        
    user_msg_timestamps[user_id].append(current_time)

    # --- GRUDGE SYSTEM: Check if Reze is ignoring this user ---
    if not ai.mirror_active:
        if user_id in grudge_list:
            if current_time < grudge_list[user_id]:
                # She's still mad. Complete silence.
                return
            else:
                # Grudge expired
                del grudge_list[user_id]
        
        # --- GRUDGE TRIGGER: If someone pings her 4+ times in 60 seconds, she holds a grudge ---
        recent_pings = [t for t in user_msg_timestamps[user_id] if current_time - t < bot_config.get('grudge_trigger_window', 60)]
        if len(recent_pings) >= bot_config.get('grudge_trigger_count', 4) and user_id not in grudge_list:
            grudge_list[user_id] = current_time + random.randint(bot_config.get('grudge_duration_min', 300), bot_config.get('grudge_duration_max', 600))
            try:
                await message.add_reaction("🙄")
            except:
                pass
            return

    # Clean the content
    content = message.content
    for mention in message.mentions:
        content = content.replace(f"<@{mention.id}>", f"@{mention.display_name}").replace(f"<@!{mention.id}>", f"@{mention.display_name}")
    clean_content = content.strip()

    # --- ATTACHMENT ERROR HANDLING & STRICT LIMITS ---
    MAX_FILES = bot_config.get('max_files_per_message', 3)
    MAX_SIZE_MB = bot_config.get('max_file_size_mb', 8)
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

    if len(message.attachments) > MAX_FILES:
        await message.reply(f"are you crazy? i'm not looking at {len(message.attachments)} files at once. keep it to {MAX_FILES} or less lol.")
        return

    attachments_data = []
    for attachment in message.attachments:
        if attachment.size > MAX_SIZE_BYTES:
            await message.reply(f"ew, that file is way too huge. keep it under {MAX_SIZE_MB}MB or i'm ignoring it.")
            return

        # Strict Sanitization: If it's not a standard image, throw it out.
        if attachment.content_type not in ALLOWED_MIME_TYPES:
            await message.reply("what even is that format? just send a normal image or i'm ignoring it.")
            return
            
        file_bytes = await attachment.read()
        attachments_data.append({
            "data": file_bytes,
            "mime_type": attachment.content_type
        })

    # --- REPLY CONTEXT: Fetch referenced message content + images ---
    reply_context = ""
    if message.reference:
        ref_msg = message.reference.resolved
        if ref_msg is None:
            try:
                ref_msg = await message.channel.fetch_message(message.reference.message_id)
            except:
                ref_msg = None
        if isinstance(ref_msg, discord.Message):
            reply_context = f"[REPLYING TO {ref_msg.author.display_name}]: {ref_msg.content}"
            # Also grab images from the replied-to message
            for att in ref_msg.attachments:
                if att.content_type in ALLOWED_MIME_TYPES and att.size <= MAX_SIZE_BYTES and len(attachments_data) < MAX_FILES:
                    try:
                        file_bytes = await att.read()
                        attachments_data.append({"data": file_bytes, "mime_type": att.content_type})
                    except:
                        pass

    # Don't return if they sent an image/video without text
    if not clean_content and not attachments_data and is_mentioned:
        await message.reply("what?")
        return
    elif not clean_content and not attachments_data:
        return

    # --- LEFT ON READ: Dry text detection ---
    # If the message is just a dry one-word reply, she might just react and not respond
    if not ai.mirror_active:
        stripped_msg = re.sub(r'[^a-zA-Z]', '', clean_content).lower()
        if stripped_msg in DRY_TEXTS and not attachments_data:
            # 50% chance to just leave them on read with a reaction
            if random.random() < bot_config.get('left_on_read_react_chance', 0.50):
                try:
                    reaction = random.choice(bot_config.get('left_on_read_reactions', LEFT_ON_READ_REACTIONS))
                    await message.add_reaction(reaction)
                except:
                    pass
                return
            # additional chance to just completely ignore (true left on read)
            elif random.random() < bot_config.get('left_on_read_ignore_chance', 0.20):
                return

    # Track activity for unprompted message system
    channel_last_activity[channel_id] = current_time
    # Clear "waiting for reply" flag — someone talked, so she can eventually bored-text again later
    unprompted_waiting_for_reply[channel_id] = False


    # Format the message for context (User Identity Parsing)
    formatted_user_message = f"[{message.author.display_name}]: {clean_content}"
    if reply_context:
        formatted_user_message = f"{reply_context}\n{formatted_user_message}"

    # (Late reply simulation removed to eliminate response delay)
    
    
    # --- ENERGY MATCHING: Detect if user is hyped (ALL CAPS, excited) ---
    energy_context = ""
    caps_ratio = sum(1 for c in clean_content if c.isupper()) / max(len(clean_content), 1)
    if caps_ratio > 0.7 and len(clean_content) > 3:
        energy_context = "[ENERGY: The user is typing in ALL CAPS. They are clearly excited, angry, or hyped. MATCH THEIR ENERGY. Reply with equal intensity — caps, exclamation marks, keyboard smashes (like 'ASJDHAKSJD') are all fair game. Do NOT be calm and lowercase when they're screaming at you.]"
    elif clean_content.endswith("?" * 2) or clean_content.endswith("!" * 2):
        energy_context = "[ENERGY: The user seems very emphatic (multiple punctuation). Be slightly more expressive than usual.]"

    # Acquire per-channel lock to prevent response interleaving
    if channel_id not in channel_locks:
        channel_locks[channel_id] = asyncio.Lock()
    await channel_locks[channel_id].acquire()

    try:
        async with message.channel.typing():
            # Extract User Context (Nickname, Role, Pronouns)
            nickname = message.author.display_name
            role_name = "unknown"
            pronouns = "they/them"
            is_hinglish_user = False

            if message.guild and isinstance(message.author, discord.Member):
                # Get per-server role config (falls back to hardcoded defaults)
                g_cfg = await get_guild_config(message.guild.id)
                hinglish_rid = get_role_id(g_cfg, 'hinglish_role_id', DEFAULT_HINGLISH_ROLE_ID)
                male_rid = get_role_id(g_cfg, 'male_role_id', DEFAULT_MALE_ROLE_ID)
                female_rid = get_role_id(g_cfg, 'female_role_id', DEFAULT_FEMALE_ROLE_ID)
                lewd_rid = get_role_id(g_cfg, 'lewd_role_id', DEFAULT_LEWD_ROLE_ID)

                # Check for Hinglish role
                is_hinglish_user = any(role.id == hinglish_rid for role in message.author.roles)
                
                # Check for Gender roles
                if any(role.id == male_rid for role in message.author.roles):
                    role_name = "male"
                    pronouns = "he/him"
                elif any(role.id == female_rid for role in message.author.roles):
                    role_name = "female"
                    pronouns = "she/her"
                    
                is_lewd_allowed = any(role.id == lewd_rid for role in message.author.roles)
            else:
                is_lewd_allowed = False

            user_context = f"Member: {nickname}, Role: {role_name}, Pronouns: {pronouns}, LewdAllowed: {is_lewd_allowed}"

            # --- ADMIN MODERATION PRE-SCAN ---
            mod_meta = ""
            is_admin = message.guild is not None and hasattr(message.author, 'guild_permissions') and message.author.guild_permissions.administrator
            if is_admin:
                content_lower = clean_content.lower()
                mod_action_type = None
                if "kick" in content_lower: mod_action_type = "KICK"
                elif "ban" in content_lower: mod_action_type = "BAN"
                elif "timeout" in content_lower: mod_action_type = "TIMEOUT"
                
                if mod_action_type:
                    target_member = None
                    non_bot_mentions = [m for m in message.mentions if m.id != bot.user.id]
                    if non_bot_mentions:
                        target_member = non_bot_mentions[0]
                    
                    if not target_member:
                        mod_meta = f"[MOD_META: ACTION={mod_action_type}, TARGET=MISSING]"
                    else:
                        # Check Hierarchy & Permissions
                        bot_member = message.guild.me
                        # Reze can only kick/ban if she is higher and target isn't an admin
                        can_execute = bot_member.top_role > target_member.top_role and not target_member.guild_permissions.administrator
                        
                        duration_info = ""
                        if mod_action_type == "TIMEOUT":
                            nums = re.findall(r'\d+', content_lower)
                            if nums:
                                duration_info = f", DURATION={nums[0]}m"
                            else:
                                duration_info = ", DURATION=MISSING"
                                
                        mod_meta = f"[MOD_META: ACTION={mod_action_type}, TARGET_ID={target_member.id}, TARGET_NAME={target_member.display_name}, CAN_EXECUTE={can_execute}{duration_info}]"

            if mod_meta:
                user_context += f"\n{mod_meta}\n"

            # --- Status Roasting Logic (15% chance) ---
            status_context = ""
            if not ai.mirror_active:
                if random.random() < bot_config.get('status_roast_chance', 0.15) and isinstance(message.author, discord.Member):
                    activities = message.author.activities
                    if activities:
                        interesting = [a for a in activities if isinstance(a, (discord.Spotify, discord.Game, discord.CustomActivity))]
                        if interesting:
                            target = random.choice(interesting)
                            if isinstance(target, discord.Spotify):
                                status_context = f"Listening to '{target.title}' by '{target.artist}' on Spotify"
                            elif isinstance(target, discord.Game):
                                status_context = f"Playing {target.name}"
                            elif isinstance(target, discord.CustomActivity):
                                status_context = f"Custom Status: '{target.name}'"
            
            # --- Server Emoji Awareness (Unlocked only) ---
            server_emojis = []
            if not ai.mirror_active and message.guild:
                server_emojis = [f":{e.name}:" for e in message.guild.emojis if e.available]
            
            if not ai.mirror_active:
                if status_context:
                    user_context += f", Current Activity: {status_context} (Note: feel free to roast this if you want, but don't force it)"
                if server_emojis:
                    user_context += f", Available Server Emojis: {', '.join(server_emojis[:20])}" # Limit to avoid token bloat

            # Inject energy context into user_context
            if energy_context:
                user_context += f"\n{energy_context}\n"

            # --- USER RELATIONSHIP TRACKING ---
            user_id_str = str(user_id)
            server_name = message.guild.name if message.guild else None
            channel_name = message.channel.name if hasattr(message.channel, 'name') else "DM"
            previous_user_data = await db.update_user_interaction(user_id_str, nickname, server_name, channel_name, clean_content)

            # --- CREATOR DETECTION ---
            is_creator = user_id in CREATOR_DISCORD_IDS or (message.author.name and message.author.name.lower() in CREATOR_USERNAMES)
            if not ai.mirror_active and is_creator:
                user_context += "\n[CREATOR: This is your creator. You recognize them. Be slightly more real with them — less guarded, more honest. You have a quiet respect for them. Don't bring up the creator thing yourself, but if they mention it, acknowledge it naturally. You're still YOU, just... a little less walls-up with this person.]\n"

            relationship_context = ""
            if not ai.mirror_active:
                if previous_user_data:
                    total_msgs = previous_user_data.get("total_messages", 0)
                    streak = previous_user_data.get("streak_days", 0)
                    closeness = previous_user_data.get("closeness", 0)
                    user_notes = previous_user_data.get("notes", "")
                    last_seen = previous_user_data.get("last_seen")
                    last_server = previous_user_data.get("last_server", "")
                    recent_servers = previous_user_data.get("recent_servers", [])
                    user_memory = previous_user_data.get("user_memory", "")

                    # Return detection
                    if last_seen:
                        try:
                            if last_seen.tzinfo is None:
                                last_seen = last_seen.replace(tzinfo=timezone.utc)
                            days_away = (datetime.now(timezone.utc) - last_seen).days
                            if days_away >= 3:
                                relationship_context += f"[RETURN: {nickname} hasn't talked to you in {days_away} days. Comment briefly — 'oh you're alive', 'thought you died', 'where have you been'.]\n"
                        except:
                            pass

                    # Cross-server awareness
                    current_location = f"{server_name}/#{channel_name}" if server_name else "DM"
                    if last_server and last_server != current_location:
                        relationship_context += f"[SERVER SWITCH: {nickname} was last talking to you in {last_server}, now they're in {current_location}. You remember them from before. You can casually reference it if natural — 'oh you're here now', 'weren't you just in the other server' — but don't force it every time.]\n"
                    if len(recent_servers) > 1:
                        relationship_context += f"[CROSS-SERVER HISTORY: You've talked to {nickname} in these places: {', '.join(recent_servers[-5:])}. You remember ALL of these conversations.]\n"

                    # Streak context
                    if streak >= 7:
                        relationship_context += f"[STREAK: {nickname} has talked to you {streak} days in a row. You're comfortable — lazier texts, inside jokes, more real.]\n"

                    # Closeness context
                    if closeness >= 7:
                        relationship_context += f"[CLOSE FRIEND: Very close with {nickname} ({total_msgs} msgs). Be more personal, meaner (they know you don't mean it), more vulnerable.]\n"
                    elif closeness >= 4:
                        relationship_context += f"[FAMILIAR: Know {nickname} decently ({total_msgs} msgs). Comfortable but not BFFs.]\n"
                    elif total_msgs is not None and total_msgs <= 3:
                        relationship_context += f"[NEW PERSON: Barely know {nickname}. Be slightly guarded, less personal.]\n"

                    # User relationship notes (per-channel)
                    if user_notes:
                        relationship_context += f"[YOUR MEMORY OF THIS PERSON (channel): {user_notes}]\n"

                    # Cross-server user memory (global)
                    if user_memory:
                        relationship_context += f"[YOUR GLOBAL MEMORY OF THIS PERSON (across all servers): {user_memory}]\n"
                else:
                    relationship_context += f"[FIRST MEETING: Never talked to {nickname} before. Be naturally curious but guarded.]\n"

                if relationship_context:
                    user_context += f"\n{relationship_context}"

            # --- LINK/URL AWARENESS ---
            if not ai.mirror_active:
                url_pattern = r'https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
                urls_found = re.findall(url_pattern, clean_content)
                if urls_found:
                    domain = urls_found[0].lower()
                    if "youtube" in domain or "youtu.be" in domain:
                        user_context += "\n[LINK: User sent a YouTube link. React naturally — 'what is this', 'i'm not watching that rn', 'is it good?', or ignore.]\n"
                    elif "twitter" in domain or "x.com" in domain:
                        user_context += "\n[LINK: User sent a Twitter/X link. React — 'twitter links are always unhinged', 'what did i just read', etc.]\n"
                    elif "tiktok" in domain:
                        user_context += "\n[LINK: User sent a TikTok. React — 'send it properly', 'is this the one everyone's posting', etc.]\n"
                    elif "instagram" in domain:
                        user_context += "\n[LINK: User sent an Instagram link. React — 'whose insta is this', 'stalking people?', etc.]\n"
                    elif "spotify" in domain:
                        user_context += "\n[LINK: User sent a Spotify link. React — 'ok let me check', 'your music taste is...', etc.]\n"
                    else:
                        user_context += f"\n[LINK: User sent a link to {domain}. Acknowledge it naturally or ignore.]\n"

            # --- GROUP CONVERSATION CONTEXT ---
            if not is_dm and message.guild:
                try:
                    recent_others = []
                    async for msg in message.channel.history(limit=5, before=message):
                        if not msg.author.bot and msg.author.id != user_id:
                            recent_others.append(f"[{msg.author.display_name}]: {msg.content[:100]}")
                    if recent_others:
                        user_context += "\n[RECENT CHANNEL CONTEXT — other people talking nearby:]\n" + "\n".join(reversed(recent_others)) + "\n[You can acknowledge, take sides, or ignore. Address different people differently.]\n"
                except:
                    pass

            # --- PERSONALITY MIRRORING STYLE GUIDE ---
            if ai.mirror_active and ai.mirror_profile:
                user_context += f"\n[PERSONALITY MIRROR ACTIVE: You are mirroring {ai.mirror_target_name}'s texting style. Keep your core Reze personality but adopt their style guidelines:\n{ai.mirror_profile}]\n"

            # Fetch memory from MongoDB
            memory_data = await db.get_channel_memory(channel_id)
            messages = memory_data["messages"]
            long_term_summary = memory_data["summary"]

            # Get AI response
            response = await ai.get_ai_response(
                formatted_user_message,
                history=messages,
                attachments=attachments_data,
                is_hinglish=is_hinglish_user,
                user_context=user_context,
                channel_id=channel_id,
                long_term_summary=long_term_summary
            )

            # Update channel memory in MongoDB (annotate with image metadata)
            storage_msg = formatted_user_message
            if attachments_data:
                img_tags = " ".join([f"[IMAGE: {att['mime_type']}]" for att in attachments_data])
                storage_msg = f"{formatted_user_message} {img_tags}"
            await db.add_message(channel_id, "user", storage_msg)
            await db.add_message(channel_id, "assistant", response)

            # --- Rolling Summarization (Memory Compression) ---
            # If the recent message history exceeds 20 messages, spawn a background task to compress the oldest 10 into the summary
            # We enforce a lock using active_compressions to prevent multiple concurrent compression jobs for the same channel
            if len(messages) + 2 >= 20 and channel_id not in active_compressions:
                active_compressions.add(channel_id)
                async def compress_and_save():
                    try:
                        current_data = await db.get_channel_memory(channel_id)
                        current_msgs = current_data["messages"]
                        
                        if len(current_msgs) >= 20:
                            # Compress everything EXCEPT the 10 most recent messages
                            msgs_to_compress = current_msgs[:-10]
                            keep_msgs = current_msgs[-10:] # The 10 most recent stay in raw memory
                            
                            logger.info(f"Triggering background memory compression for channel {channel_id}...")
                            new_summary = await ai.compress_memory(channel_id, long_term_summary, msgs_to_compress)
                            
                            # Save the new summary and trim the raw message list
                            await db.update_summary_and_trim(channel_id, new_summary, keep_msgs)
                            logger.info(f"Memory compressed successfully for channel {channel_id}.")

                            # Also update user-level cross-server memory
                            try:
                                old_user_mem = await db.get_user_memory(user_id_str)
                                srv_info = f"{server_name}/#{channel_name}" if server_name else "DM"
                                new_user_mem = await ai.compress_user_memory(old_user_mem, new_summary, nickname, srv_info)
                                await db.update_user_memory(user_id_str, new_user_mem)
                                logger.info(f"User memory updated for {nickname} ({user_id_str}).")
                            except Exception as e:
                                logger.error(f"Failed to update user memory: {e}")
                    except Exception as e:
                        logger.error(f"Error during memory compression: {e}")
                    finally:
                        active_compressions.discard(channel_id)
                        
                bot.loop.create_task(compress_and_save())

            # Clean brackets if escaped
            response = response.replace('\\[', '[').replace('\\]', ']')

            # --- Dynamic Reaction Parsing ---
            react_match = re.search(r'\[REACT:\s*(.*?)\]', response, re.IGNORECASE)
            if react_match:
                emoji_str = react_match.group(1).strip()
                emoji_name = emoji_str.strip(':')
                
                # Hard enforcement: limit reaction spam and prevent duplicate emojis
                if channel_id not in ai.channel_state:
                    ai.channel_state[channel_id] = {}
                    
                recent_reactions = ai.channel_state[channel_id].get("recent_reactions", [])
                
                should_react = True
                if emoji_str in recent_reactions:
                    should_react = False  # Completely block back-to-back repetition
                elif random.random() > 0.4:  
                    # Even if the AI tries to react, block it 60% of the time to force rarity
                    should_react = False
                    
                if should_react:
                    # Remember the emoji to prevent immediate reuse
                    recent_reactions.append(emoji_str)
                    ai.channel_state[channel_id]["recent_reactions"] = recent_reactions[-4:] # remember last 4
                
                    # Check for custom emoji in this guild
                    custom_emoji = discord.utils.get(message.guild.emojis, name=emoji_name)
                    try:
                        if custom_emoji and custom_emoji.available:
                            await message.add_reaction(custom_emoji)
                        else:
                            # Fallback to standard emoji char or name
                            await message.add_reaction(emoji_str)
                    except Exception as e:
                        logger.error(f"Reaction Error: {e}")
            
            # --- Dynamic Moderation Tag Parsing ---
            # SAFETY NET: If AI agreed to mod action but forgot the tag, inject it
            if not ai.mirror_active and mod_meta and "CAN_EXECUTE=True" in mod_meta:
                has_mod_tag = re.search(r'\[(KICK|BAN|TIMEOUT):\s*\d+', response, re.IGNORECASE)
                if not has_mod_tag:
                    # AI forgot the tag — extract action and target from mod_meta and inject
                    meta_action = re.search(r'ACTION=(\w+)', mod_meta)
                    meta_target = re.search(r'TARGET_ID=(\d+)', mod_meta)
                    if meta_action and meta_target:
                        action_name = meta_action.group(1).upper()
                        target_id_str = meta_target.group(1)
                        if action_name == "TIMEOUT":
                            meta_dur = re.search(r'DURATION=(\d+)', mod_meta)
                            dur = meta_dur.group(1) if meta_dur else "60"
                            response += f" [{action_name}: {target_id_str}, {dur}]"
                        else:
                            response += f" [{action_name}: {target_id_str}]"
                        logger.info(f"[MOD SAFETY NET] Auto-injected {action_name} tag for target {target_id_str}")

            if not ai.mirror_active:
                mod_exec_match = re.search(r'\[(KICK|BAN|TIMEOUT):\s*(\d+)(?:,\s*(\d+))?\]', response, re.IGNORECASE)
                if mod_exec_match:
                    mod_action = mod_exec_match.group(1).upper()
                    target_id = int(mod_exec_match.group(2))
                    target_obj = message.guild.get_member(target_id)
                    
                    if target_obj:
                        bot_member = message.guild.me
                        
                        # --- DEBUG LOGGING ---
                        print(f"\n--- MOD ACTION DEBUG ---")
                        print(f"Action: {mod_action} on {target_obj.display_name}")
                        print(f"Bot has Administrator: {bot_member.guild_permissions.administrator}")
                        print(f"Bot has Ban Members: {bot_member.guild_permissions.ban_members}")
                        print(f"Bot Top Role: '{bot_member.top_role.name}' (Position: {bot_member.top_role.position})")
                        print(f"Target Top Role: '{target_obj.top_role.name}' (Position: {target_obj.top_role.position})")
                        print(f"------------------------\n")

                        # Re-verify hierarchy before executing
                        if bot_member.top_role <= target_obj.top_role or target_obj == message.guild.owner:
                            await message.channel.send("can't touch them... they're above me 💀")
                        else:
                            try:
                                if mod_action == "KICK":
                                    await target_obj.kick(reason="Enforced by Reze (Admin Command)")
                                elif mod_action == "BAN":
                                    await target_obj.ban(reason="Enforced by Reze (Admin Command)")
                                elif mod_action == "TIMEOUT":
                                    mins = int(mod_exec_match.group(3)) if mod_exec_match.group(3) else 60
                                    await target_obj.timeout(discord.utils.utcnow() + timedelta(minutes=mins), reason="Enforced by Reze (Admin Command)")
                                await message.channel.send("done.")
                            except discord.Forbidden as e:
                                print(f"DISCORD FORBIDDEN: {e}")
                                await message.channel.send("i literally have admin but discord won't let me 😭 move my role higher in settings")
                            except Exception as mod_err:
                                logger.error(f"Moderation Action Failed: {mod_err}")

            # Strip reaction and moderation tags from response
            response = re.sub(r'\[(?:REACT|KICK|BAN|TIMEOUT):.*?\]', '', response, flags=re.IGNORECASE | re.DOTALL).strip()

            # --- Hardcoded Image Cooldown Pipeline ---
            if channel_id not in ai.channel_state:
                ai.channel_state[channel_id] = {}
            if "image_cooldown" not in ai.channel_state[channel_id]:
                ai.channel_state[channel_id]["image_cooldown"] = 0
                
            meme_to_send = None
            is_nsfw = channel_id == "1495092765942612159" or ai.channel_state.get(channel_id, {}).get("nsfw_toggle", False)
            
            if ai.mirror_active:
                response = re.sub(r'\[(?:send_meme|fetch_web):.*?\]', '', response, flags=re.IGNORECASE | re.DOTALL).strip()
            elif ai.channel_state[channel_id]["image_cooldown"] > 0 and not is_nsfw:
                # Still in cooldown, legally strip any generated image tags so she can't send them
                ai.channel_state[channel_id]["image_cooldown"] -= 1
                response = re.sub(r'\[(?:send_meme|fetch_web):.*?\]', '', response, flags=re.IGNORECASE | re.DOTALL).strip()
            else:
                # --- Dynamic Meme Extraction ---
                meme_match = re.search(r'\[send_meme:\s*(.*?)\]', response, re.IGNORECASE | re.DOTALL)
                if meme_match:
                    meme_filename = meme_match.group(1).strip()
                    meme_path = os.path.join("assets", "memes", meme_filename)
                    if os.path.exists(meme_path):
                        meme_to_send = discord.File(meme_path)
                        
                        # Track memory
                        if channel_id not in ai.channel_state:
                            ai.channel_state[channel_id] = {}
                        if "recent_memes" not in ai.channel_state[channel_id]:
                            ai.channel_state[channel_id]["recent_memes"] = []
                            
                        ai.channel_state[channel_id]["recent_memes"].append(meme_filename)
                        ai.channel_state[channel_id]["recent_memes"] = ai.channel_state[channel_id]["recent_memes"][-10:]
                        if not is_nsfw:
                            ai.channel_state[channel_id]["image_cooldown"] = random.randint(2, 4)
                # --- Dynamic Web Image Extraction ---
                web_meme_match = re.search(r'\[fetch_web:\s*(.*?)\]', response, re.IGNORECASE | re.DOTALL)
                if web_meme_match and not meme_to_send:
                    query = web_meme_match.group(1).strip()
                    
                    if channel_id not in ai.channel_state:
                        ai.channel_state[channel_id] = {}
                    
                    images_found = []
                    # SFW uses Safebooru or Reddit. NSFW uses Danbooru/Gelbooru/Reddit
                    if is_nsfw:
                        source_choice = random.choice(["danbooru", "danbooru", "danbooru", "gelbooru", "gelbooru", "reddit_nsfw"])
                    else:
                        source_choice = random.choice(["safebooru", "safebooru", "reddit_broad", "reddit_specific"])
                    
                    try:
                        timeout = aiohttp.ClientTimeout(total=15) # Boosted slightly for reliability
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            headers = {'User-agent': 'RezeBot/1.0'}
                            
                            logger.info(f"[IMAGE FETCH] Source choice: {source_choice} | Query: '{query}'")
                            
                            if source_choice == "danbooru":
                                # Danbooru API — massive high-quality anime art archive (NSFW focused)
                                db_query = translate_tags(query, is_booru=True)
                                db_tags = f"{db_query} rating:explicit".strip()
                                if not query:
                                    nsfw_variety = random.choice(["", "1girl", "solo", "breasts", "cleavage", "nude"])
                                    db_tags = f"reze_(chainsaw_man) rating:explicit {nsfw_variety}".strip()
                                db_tags_encoded = urllib.parse.quote(db_tags)
                                random_page = random.randint(1, 5)
                                url = f"https://danbooru.donmai.us/posts.json?tags={db_tags_encoded}&limit=50&page={random_page}"
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        if isinstance(data, list):
                                            for post in data:
                                                file_url = post.get('file_url') or post.get('large_file_url')
                                                if file_url:
                                                    if file_url.startswith("//"):
                                                        file_url = f"https:{file_url}"
                                                    elif not file_url.startswith("http"):
                                                        file_url = f"https://danbooru.donmai.us/{file_url.lstrip('/')}"
                                                    images_found.append(file_url)
                                                    
                            elif source_choice == "gelbooru":
                                # Gelbooru API (NSFW focus)
                                gb_query = translate_tags(query, is_booru=True)
                                gb_tags = f"{gb_query} rating:explicit".strip()
                                gb_query_encoded = urllib.parse.quote(gb_tags)
                                random_pid = random.randint(0, 10)
                                url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags={gb_query_encoded}&limit=50&pid={random_pid}"
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        if "post" in data:
                                            for p in data['post']:
                                                f_url = p.get('file_url')
                                                if f_url:
                                                    if f_url.startswith("//"):
                                                        f_url = f"https:{f_url}"
                                                    elif not f_url.startswith("http"):
                                                        f_url = f"https://gelbooru.com/{f_url.lstrip('/')}"
                                                    images_found.append(f_url)
                                                    
                            elif source_choice == "safebooru":
                                # Safebooru API (SFW Anime focus)
                                sb_query = translate_tags(query, is_booru=True)
                                sb_tags = f"{sb_query} rating:general".strip()
                                sb_query_encoded = urllib.parse.quote(sb_tags)
                                random_pid = random.randint(0, 5)
                                url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags={sb_query_encoded}&limit=50&pid={random_pid}"
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        if isinstance(data, list):
                                            for p in data:
                                                f_url = p.get('file_url') or p.get('image')
                                                if f_url:
                                                    if f_url.startswith("//"):
                                                        f_url = f"https:{f_url}"
                                                    elif not f_url.startswith("http"):
                                                        f_url = f"https://safebooru.org/images/{p.get('directory')}/{p.get('image')}"
                                                    images_found.append(f_url)
                                                    
                            elif source_choice == "reddit_broad":
                                # Broad reddit search (SFW)
                                safe_query = urllib.parse.quote(translate_tags(query, is_booru=False))
                                url = f"https://www.reddit.com/r/ChainsawMan/search.json?q={safe_query}&restrict_sr=on&include_over_18=off&limit=50"
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        posts = data.get('data', {}).get('children', [])
                                        images_found = [p['data']['url'] for p in posts if p['data'].get('url') and p['data']['url'].startswith('https://i.redd.it/')]
                                        
                            elif source_choice == "reddit_specific":
                                # Specific Reze subreddits (SFW)
                                safe_query = urllib.parse.quote(translate_tags(query, is_booru=False))
                                url = f"https://www.reddit.com/r/ChainsawMan+RezeCult/search.json?q={safe_query}&restrict_sr=on&include_over_18=off&limit=60"
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        posts = data.get('data', {}).get('children', [])
                                        images_found = [p['data']['url'] for p in posts if p['data'].get('url') and p['data']['url'].startswith('https://i.redd.it/')]
                                                    
                            elif source_choice == "reddit_nsfw":
                                # NSFW Reddit subreddits
                                safe_query = urllib.parse.quote(translate_tags(query, is_booru=False))
                                url = f"https://www.reddit.com/r/ChainsawManNSFW+hentai/search.json?q={safe_query}&restrict_sr=on&include_over_18=on&limit=60"
                                async with session.get(url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        posts = data.get('data', {}).get('children', [])
                                        images_found = [p['data']['url'] for p in posts if p['data'].get('url') and p['data']['url'].startswith('https://i.redd.it/')]

                            # Standardize file extension check and strip query strings
                            valid_images = []
                            for img in images_found:
                                clean_img = img.split('?')[0]
                                if any(clean_img.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                                    valid_images.append(img)
                            images_found = valid_images

                            # Persistent Deduplication Check via MongoDB (Gather async queries)
                            if images_found:
                                is_sent_list = await asyncio.gather(*(db.is_image_sent(channel_id, url) for url in images_found))
                                fresh_images = [img for img, is_sent in zip(images_found, is_sent_list) if not is_sent]
                            else:
                                fresh_images = []

                            # Fallback if no fresh images are found from primary query
                            if not fresh_images:
                                logger.info(f"[IMAGE FETCH] No fresh images found for primary query. Running fallback...")
                                if is_nsfw:
                                    fb_page = random.randint(1, 15)
                                    fallback_url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags=reze_(chainsaw_man)+rating:explicit&limit=40&pid={fb_page}"
                                else:
                                    fb_page = random.randint(1, 10)
                                    fallback_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=reze_(chainsaw_man)+rating:general&limit=40&pid={fb_page}"
                                
                                async with session.get(fallback_url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        fallback_candidates = []
                                        if isinstance(data, list):
                                            for p in data:
                                                f_url = p.get('file_url') or p.get('image')
                                                if f_url:
                                                    if f_url.startswith("//"):
                                                        f_url = f"https:{f_url}"
                                                    elif not f_url.startswith("http"):
                                                        if "safebooru" in fallback_url:
                                                            f_url = f"https://safebooru.org/images/{p.get('directory')}/{p.get('image')}"
                                                        else:
                                                            f_url = f"https://danbooru.donmai.us/{f_url.lstrip('/')}"
                                                    fallback_candidates.append(f_url)
                                        elif "post" in data:
                                            for p in data['post']:
                                                f_url = p.get('file_url')
                                                if f_url:
                                                    if f_url.startswith("//"):
                                                        f_url = f"https:{f_url}"
                                                    elif not f_url.startswith("http"):
                                                        f_url = f"https://gelbooru.com/{f_url.lstrip('/')}"
                                                    fallback_candidates.append(f_url)
                                        
                                        # Deduplicate fallback images
                                        if fallback_candidates:
                                            fb_is_sent_list = await asyncio.gather(*(db.is_image_sent(channel_id, url) for url in fallback_candidates))
                                            fresh_images = [img for img, is_sent in zip(fallback_candidates, fb_is_sent_list) if not is_sent]

                            # Final execution: loop through fresh_images and try to download/send/compress
                            if fresh_images:
                                random.shuffle(fresh_images)
                                
                                max_size_bytes = 8 * 1024 * 1024
                                if message.guild:
                                    max_size_bytes = message.guild.filesize_limit
                                    
                                success = False
                                for attempt_url in fresh_images[:5]:
                                    try:
                                        logger.info(f"[IMAGE FETCH] Attempting to download: {attempt_url}")
                                        async with session.get(attempt_url, headers=headers, timeout=10) as img_resp:
                                            if img_resp.status == 200:
                                                img_data = await img_resp.read()
                                                original_size = len(img_data)
                                                file_ext = attempt_url.split('?')[0].split('.')[-1].lower()
                                                
                                                # Safety Compress / Resize using Pillow
                                                if original_size > max_size_bytes:
                                                    logger.info(f"[IMAGE FETCH] Image size ({original_size / (1024*1024):.2f}MB) exceeds server limit ({max_size_bytes / (1024*1024):.2f}MB). Attempting dynamic PIL compression...")
                                                    if file_ext != "gif":
                                                        try:
                                                            img = Image.open(io.BytesIO(img_data))
                                                            if img.width > 2400 or img.height > 2400:
                                                                img.thumbnail((2400, 2400))
                                                            if img.mode in ("RGBA", "P"):
                                                                img = img.convert("RGB")
                                                            compressed_io = io.BytesIO()
                                                            img.save(compressed_io, format="JPEG", quality=80)
                                                            compressed_data = compressed_io.getvalue()
                                                            
                                                            if len(compressed_data) < max_size_bytes:
                                                                img_data = compressed_data
                                                                file_ext = "jpg"
                                                                logger.info(f"[IMAGE FETCH] Successfully compressed static image from {original_size / (1024*1024):.2f}MB to {len(img_data) / (1024*1024):.2f}MB")
                                                            else:
                                                                logger.warning(f"[IMAGE FETCH] Compressed static image still too large ({len(compressed_data) / (1024*1024):.2f}MB). Skipping to next candidate.")
                                                                continue
                                                        except Exception as pil_err:
                                                            logger.error(f"[IMAGE FETCH] PIL compression failed: {pil_err}")
                                                            continue
                                                    else:
                                                        logger.warning(f"[IMAGE FETCH] GIF size too large and GIF compression is not supported. Skipping.")
                                                        continue
                                                
                                                meme_to_send = discord.File(io.BytesIO(img_data), f"reze_image.{file_ext}")
                                                
                                                # Save URL in MongoDB database history (Strict Persistent Deduplication!)
                                                await db.record_sent_image(channel_id, attempt_url)
                                                logger.info(f"[IMAGE FETCH] Successfully routed and saved image to channel DB: {attempt_url}")
                                                
                                                if not is_nsfw:
                                                    ai.channel_state[channel_id]["image_cooldown"] = random.randint(2, 4)
                                                
                                                success = True
                                                break
                                            else:
                                                logger.warning(f"[IMAGE FETCH] HTTP download failed (Status {img_resp.status}) for URL: {attempt_url}")
                                    except Exception as img_err:
                                        logger.error(f"[IMAGE FETCH] Error processing image candidate {attempt_url}: {img_err}")
                                
                                if not success:
                                    logger.error("[IMAGE FETCH] All 5 image download/compression candidates failed.")
                            else:
                                logger.warning("[IMAGE FETCH] No image URLs found from any source.")
                    except asyncio.TimeoutError:
                        logger.error("Web fetch timed out.")
                    except Exception as e:
                        logger.error(f"Web Fetch Error: {e}")
                
            # AGGRESSIVE CLEANUP: Remove ANY tag from response text
            response = re.sub(r'\[(?:send_meme|fetch_web|voice):.*?\]', '', response, flags=re.IGNORECASE | re.DOTALL).strip()

            # --- MENTION CONVERTER: Turn @name into real Discord pings ---
            if message.guild:
                def replace_mention(match):
                    name = match.group(1).strip()
                    # Try exact display_name match first, then fuzzy
                    for member in message.guild.members:
                        if member.display_name.lower() == name.lower() or member.name.lower() == name.lower():
                            return f"<@{member.id}>"
                    # Partial match fallback
                    for member in message.guild.members:
                        if name.lower() in member.display_name.lower() or name.lower() in member.name.lower():
                            return f"<@{member.id}>"
                    return match.group(0)  # No match, leave as-is
                response = re.sub(r'@(\w+)', replace_mention, response)

            # --- Multi-Message Splitter & Typo Generator ---
            # Group by newlines instead of every single period to avoid 5-message spam
            sentences = [s.strip() for s in response.split('\n') if s.strip()]
            if not sentences:
                sentences = [response] if response else []

            # Smart cap on multi-messages: real people don't send 6 texts in a row
            current_mood = ai.get_raw_mood(channel_id)
            max_messages = 5 if current_mood in ["DRUNK", "YAPPING"] else 3
            if len(sentences) > max_messages:
                # Merge excess lines into the last allowed message
                overflow = " ".join(sentences[max_messages - 1:])
                sentences = sentences[:max_messages - 1] + [overflow]

            # If she ONLY sent media and no text
            if not sentences and meme_to_send:
                await message.reply(file=meme_to_send)
                return

            now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
            is_drunk_hours = (now.weekday() in [4, 5] and now.hour >= 22) or (now.weekday() in [5, 6] and now.hour < 3)

            for i, sentence in enumerate(sentences):
                # --- TYPING HESITATION (15% chance on longer messages) ---
                if len(sentence) > 20 and random.random() < bot_config.get('typing_hesitation_chance', 0.15):
                    # She starts typing, stops, then types again
                    async with message.channel.typing():
                        await asyncio.sleep(random.uniform(1.5, 3.0))  # typing...
                    # Gap where she "deleted what she was writing"
                    await asyncio.sleep(random.uniform(1.0, 2.0))
                    # Starts typing again
                    async with message.channel.typing():
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                else:
                    # Normal typing delay
                    delay = min(len(sentence) / 15.0, 3.0)
                    if i > 0:
                        async with message.channel.typing():
                            await asyncio.sleep(delay)
                
                # --- NEW: Robust Typo Generator (5% or 25% chance) ---
                has_typo = False
                original_word = ""
                final_sentence = sentence
                
                if not ai.mirror_active:
                    typo_chance = bot_config.get('typo_chance_drunk', 0.25) if is_drunk_hours else bot_config.get('typo_chance_normal', 0.05)
                    if random.random() < typo_chance:
                        words = sentence.split()
                        if len(words) > 3:
                            idx = random.randint(0, len(words)-1)
                            raw_word = words[idx]
                            # Only target words with letters (no lone punctuation)
                            clean_word = re.sub(r'[^a-zA-Z]', '', raw_word)
                            if len(clean_word) > 4:
                                original_word = clean_word
                                # swap two middle letters
                                swap_pos = random.randint(1, len(clean_word)-2)
                                typo_clean = clean_word[:swap_pos] + clean_word[swap_pos+1] + clean_word[swap_pos] + clean_word[swap_pos+2:]
                                
                                if typo_clean != clean_word:
                                    typo_word = raw_word.replace(clean_word, typo_clean)
                                    words[idx] = typo_word
                                    final_sentence = " ".join(words)
                                    has_typo = True


                if i == 0:
                    try:
                        if meme_to_send:
                            sent_msg = await message.reply(final_sentence, file=meme_to_send)
                            meme_to_send = None
                        else:
                            sent_msg = await message.reply(final_sentence)
                    except discord.errors.HTTPException as e:
                        if e.code == 50035: # Unknown Message (deleted)
                            if meme_to_send:
                                sent_msg = await message.channel.send(final_sentence, file=meme_to_send)
                                meme_to_send = None
                            else:
                                sent_msg = await message.channel.send(final_sentence)
                        else:
                            raise e
                else:
                    sent_msg = await message.channel.send(final_sentence)
                    
                if has_typo:
                    async with message.channel.typing():
                        await asyncio.sleep(1.0)
                        await sent_msg.reply(f"*{original_word}")

                # --- MESSAGE EDITING: She "fixes" something after sending (4% chance) ---
                if not ai.mirror_active and random.random() < bot_config.get('message_edit_chance', 0.04) and len(final_sentence) > 15:
                    await asyncio.sleep(random.uniform(3.0, 8.0))
                    edited = final_sentence
                    # Try to find something to "fix"
                    edit_made = False
                    for old, new in EDIT_SWAPS:
                        # Only replace whole word matches
                        pattern = rf'\b{re.escape(old)}\b'
                        if re.search(pattern, edited):
                            edited = re.sub(pattern, new, edited, count=1)
                            edit_made = True
                            break
                    if not edit_made:
                        # Just add/remove a period or rephrase slightly
                        if edited.endswith('.'):
                            edited = edited[:-1]
                        else:
                            edited = edited + '.'  
                        edit_made = True
                    if edit_made:
                        try:
                            await sent_msg.edit(content=edited)
                        except:
                            pass

                # --- MESSAGE DELETION REGRET ---
                # She sends something, immediately regrets it, deletes it
                if not ai.mirror_active:
                    delete_chance = bot_config.get('message_delete_chance_drunk', 0.10) if is_drunk_hours else bot_config.get('message_delete_chance_normal', 0.015)
                    if random.random() < delete_chance and i == 0 and len(sentences) == 1:
                        await asyncio.sleep(random.uniform(1.5, 4.0))
                        try:
                            await sent_msg.delete()
                            await asyncio.sleep(random.uniform(1.0, 3.0))
                            # If someone asks "what did you say", she deflects
                            nothing_responses = ["nothing", "nvm", "forget it", "wasn't important", "dw about it"]
                            await message.channel.send(random.choice(nothing_responses))
                        except:
                            pass

            # --- SCREENSHOT PARANOIA ---
            if not ai.mirror_active and random.random() < bot_config.get('screenshot_paranoia_chance', 0.04) and len(response) > 50:
                is_vulnerable = any(w in response.lower() for w in ["miss", "love", "cute", "care", "feel", "sorry", "sad", "like you"])
                is_nsfw_ctx = ai.channel_state.get(channel_id, {}).get("nsfw_toggle", False)
                if is_vulnerable or is_nsfw_ctx:
                    await asyncio.sleep(random.uniform(1.5, 4.0))
                    ss_responses = ["don't ss that", "if you screenshot this i will find you", "that stays between us", "don't you dare screenshot", "delete that from your brain"]
                    await message.channel.send(random.choice(ss_responses))

    except Exception as e:
        logger.error(f"Generation Error: {e}")
        # --- NEW: Randomized Fallback Responses on Error ---
        try:
            await message.reply(random.choice(FALLBACK_MESSAGES))
        except:
            await message.channel.send(random.choice(FALLBACK_MESSAGES))
    finally:
        if channel_id in channel_locks:
            try:
                channel_locks[channel_id].release()
            except RuntimeError:
                pass  # Lock wasn't acquired (edge case)

# --- BACKGROUND TASK: Unprompted Messages (Bored Reze) ---
# Tracks whether Reze already sent an unanswered bored message (per channel)
unprompted_waiting_for_reply = {}

async def unprompted_message_loop():
    """Every few minutes, check if a target channel has been dead. If so, Reze might text first."""
    await bot.wait_until_ready()
    TARGET_CHANNEL_ID = 1492604782874067075  # The channel she hangs out in
    IST = timezone(timedelta(hours=5, minutes=30))
    
    while not bot.is_closed():
        try:
            # Wait between checks
            await asyncio.sleep(random.randint(bot_config.get('unprompted_min_interval', 1800), bot_config.get('unprompted_max_interval', 3600)))
            
            if ai.mirror_active:
                continue
            
            if not bot_config.get('unprompted_enabled', True):
                continue
            
            # Only do this during "awake" hours (8 AM - 1 AM IST)
            now = datetime.now(IST)
            if now.hour < 8 or (now.hour >= 1 and now.hour < 6):
                continue
                
            channel = bot.get_channel(TARGET_CHANNEL_ID)
            if not channel:
                continue
            
            channel_id = str(TARGET_CHANNEL_ID)
            
            # ANTI-FLOOD: If she already sent a bored message and nobody replied, DON'T send another
            if unprompted_waiting_for_reply.get(channel_id, False):
                continue
            
            # Global cooldown: don't send if a recent event message was sent
            if time.time() - last_event_message_time < EVENT_COOLDOWN_SECONDS:
                continue
            
            # Check if channel has been dead for at least 45 minutes
            last_activity = channel_last_activity.get(channel_id, 0)
            if time.time() - last_activity < 2700:  # Less than 45 min since last msg
                continue
            
            # 25% chance to actually send something
            if random.random() > bot_config.get('unprompted_chance', 0.25):
                continue
                
            # Generate an unprompted message
            msg = await ai.generate_unprompted_message(channel_id)
            if msg:
                async with channel.typing():
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                await channel.send(msg)
                # Mark that she's waiting for a reply — she won't text again until someone responds
                unprompted_waiting_for_reply[channel_id] = True
                last_event_message_time = time.time()
                print(f"[UNPROMPTED] Reze sent a bored message in #{channel.name} (waiting for reply)")
                
        except Exception as e:
            logger.error(f"Unprompted message loop error: {e}")
            await asyncio.sleep(60)

# --- BACKGROUND TASK: Story / Status Posting ---
async def story_posting_loop():
    """Posts an Instagram-style story (image + short caption) once a day."""
    await bot.wait_until_ready()
    STORY_CHANNEL_ID = 1346667584669487224
    IST = timezone(timedelta(hours=5, minutes=30))
    first_run = True
    
    while not bot.is_closed():
        try:
            if not first_run:
                # Wait between stories
                await asyncio.sleep(random.randint(bot_config.get('story_min_interval', 43200), bot_config.get('story_max_interval', 86400)))
            else:
                # Wait a bit after boot, then post the first story to prove it works
                await asyncio.sleep(45)
                first_run = False
                
            if ai.mirror_active:
                continue
                
            now = datetime.now(IST)
            # Only post during reasonable hours (e.g. not between 2 AM and 8 AM)
            if now.hour >= 2 and now.hour < 8:
                continue

            channel = bot.get_channel(STORY_CHANNEL_ID)
            if not channel:
                continue

            response = await ai.generate_story()
            if not response:
                continue
                
            meme_to_send = None
            web_meme_match = re.search(r'\[fetch_web:\s*(.*?)\]', response, re.IGNORECASE | re.DOTALL)
            if web_meme_match:
                query = web_meme_match.group(1).strip()
                clean_query = query.lower().replace("reze", "").strip()
                
                timeout = aiohttp.ClientTimeout(total=10)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    headers = {'User-agent': 'RezeBot/1.0'}
                    safe_query = urllib.parse.quote(f"reze_(chainsaw_man) {clean_query}")
                    url = f"https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1&tags={safe_query}+rating:general&limit=50"
                    
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if "post" in data:
                                images = [p['file_url'] for p in data['post'] if "file_url" in p]
                                if images:
                                    img_url = random.choice(images)
                                    async with session.get(img_url) as img_resp:
                                        if img_resp.status == 200:
                                            img_data = await img_resp.read()
                                            file_ext = img_url.split('?')[0].split('.')[-1]
                                            meme_to_send = discord.File(io.BytesIO(img_data), f"story.{file_ext}")

            caption = re.sub(r'\[fetch_web:.*?\]', '', response, flags=re.IGNORECASE).strip()
            
            if meme_to_send:
                async with channel.typing():
                    await asyncio.sleep(3)
                await channel.send(caption, file=meme_to_send)
                print(f"[STORY] Reze posted a story to #{channel.name}")

        except Exception as e:
            logger.error(f"Story posting loop error: {e}")
            await asyncio.sleep(60)

# --- BACKGROUND TASK: Wrong Chat Mistake ---
async def wrong_chat_loop():
    """Very rarely, Reze sends a message to the wrong chat, deletes it, and says 'mb wrong chat'."""
    await bot.wait_until_ready()
    TARGET_CHANNEL_ID = 1492604782874067075
    IST = timezone(timedelta(hours=5, minutes=30))
    
    while not bot.is_closed():
        try:
            # Check every 2-5 hours
            await asyncio.sleep(random.randint(bot_config.get('wrong_chat_min_interval', 7200), bot_config.get('wrong_chat_max_interval', 18000)))
            
            if ai.mirror_active:
                continue
                
            # Only during active hours
            now = datetime.now(IST)
            if now.hour < 10 or now.hour >= 23:
                continue
            
            # 15% chance when the timer fires (so roughly once every 1-2 days)
            if not bot_config.get('wrong_chat_enabled', True) or random.random() > bot_config.get('wrong_chat_chance', 0.15):
                continue
                
            channel = bot.get_channel(TARGET_CHANNEL_ID)
            if not channel:
                continue
            
            # Send the "wrong" message
            wrong_msg = random.choice(WRONG_CHAT_MESSAGES)
            sent = await channel.send(wrong_msg)
            
            # Wait 2-5 seconds, then delete it
            await asyncio.sleep(random.uniform(2.0, 5.0))
            await sent.delete()
            
            # Then send the correction
            await asyncio.sleep(random.uniform(0.5, 1.5))
            corrections = ["mb wrong chat", "wrong chat lol", "oops wrong chat", "ignore that", "that wasn't for here 💀"]
            await channel.send(random.choice(corrections))
            print(f"[WRONG CHAT] Reze sent a wrong-chat message in #{channel.name}")
            
        except Exception as e:
            logger.error(f"Wrong chat loop error: {e}")
            await asyncio.sleep(300)

# --- BACKGROUND TASK: Discord Rich Presence Cycling ---
async def status_cycling_loop():
    """Cycle Reze's Discord status throughout the day to look like a real user."""
    await bot.wait_until_ready()
    IST = timezone(timedelta(hours=5, minutes=30))
    last_hour = -1
    
    while not bot.is_closed():
        try:
            if ai.mirror_active:
                await asyncio.sleep(30)
                continue
                
            now = datetime.now(IST)
            current_hour = now.hour
            
            # Only update when the hour changes
            if current_hour != last_hour:
                last_hour = current_hour
                
                # Sleep hours: go DND/Idle
                if 2 <= current_hour < 7:
                    await bot.change_presence(
                        status=discord.Status.idle,
                        activity=discord.CustomActivity(name="💤")
                    )
                    print(f"[STATUS] Reze is sleeping (idle)")
                elif current_hour in STATUS_SCHEDULE:
                    activity_type, activity_name = STATUS_SCHEDULE[current_hour]
                    
                    if activity_type == discord.ActivityType.custom:
                        activity = discord.CustomActivity(name=activity_name)
                    elif activity_type == discord.ActivityType.playing:
                        activity = discord.Game(name=activity_name)
                    elif activity_type == discord.ActivityType.listening:
                        activity = discord.Activity(type=discord.ActivityType.listening, name=activity_name)
                    elif activity_type == discord.ActivityType.watching:
                        activity = discord.Activity(type=discord.ActivityType.watching, name=activity_name)
                    else:
                        activity = discord.CustomActivity(name=activity_name)
                    
                    await bot.change_presence(status=discord.Status.online, activity=activity)
                    print(f"[STATUS] Reze is now: {activity_name}")
                else:
                    await bot.change_presence(status=discord.Status.online, activity=None)
            
            # Check every 5 minutes
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Status cycling error: {e}")
            await asyncio.sleep(60)

# --- SERVER EVENT HANDLERS ---

@bot.event
async def on_member_join(member):
    """React to new members joining the server."""
    if ai.mirror_active:
        return
    global last_event_message_time
    if member.bot:
        return
    TARGET_CHANNEL_ID = 1492604782874067075
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        return
    # Global cooldown: don't flood the chat with event messages
    if time.time() - last_event_message_time < EVENT_COOLDOWN_SECONDS:
        return
    if random.random() < 0.15:  # Reduced from 0.3
        await asyncio.sleep(random.uniform(15, 60))  # Longer delay
        responses = ["who's this", "new person 👀", "oh hey", "another one", f"welcome ig {member.display_name}", "hi", "oh"]
        await channel.send(random.choice(responses))
        last_event_message_time = time.time()

@bot.event
async def on_member_remove(member):
    """React to members leaving the server."""
    if ai.mirror_active:
        return
    global last_event_message_time
    if member.bot:
        return
    TARGET_CHANNEL_ID = 1492604782874067075
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        return
    # Global cooldown: don't flood the chat with event messages
    if time.time() - last_event_message_time < EVENT_COOLDOWN_SECONDS:
        return
    if random.random() < 0.10:  # Reduced from 0.25
        await asyncio.sleep(random.uniform(10, 30))
        responses = ["lol they left", "rip", "bye ig", "💀", f"{member.display_name} left lmao", "another one gone"]
        await channel.send(random.choice(responses))
        last_event_message_time = time.time()

@bot.event
async def on_member_update(before, after):
    """React to nickname changes."""
    if ai.mirror_active:
        return
    global last_event_message_time
    if before.bot:
        return
    if before.nick != after.nick and after.nick is not None:
        TARGET_CHANNEL_ID = 1492604782874067075
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel and time.time() - last_event_message_time >= EVENT_COOLDOWN_SECONDS and random.random() < 0.12:
            await asyncio.sleep(random.uniform(20, 90))
            responses = [
                "why did you change your name 💀",
                "new name who dis",
                f"\"{after.display_name}\" ok sure",
                "i liked the old one better ngl"
            ]
            await channel.send(random.choice(responses))
            last_event_message_time = time.time()

@bot.event
async def on_voice_state_update(member, before, after):
    """React to voice channel joins/leaves."""
    if ai.mirror_active:
        return
    global last_event_message_time
    if member.bot:
        return
    TARGET_CHANNEL_ID = 1492604782874067075
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        return
    # Global cooldown
    if time.time() - last_event_message_time < EVENT_COOLDOWN_SECONDS:
        return
    # Someone joined VC
    if before.channel is None and after.channel is not None:
        if random.random() < 0.08:  # Reduced from 0.12
            await asyncio.sleep(random.uniform(20, 90))
            responses = [
                "yall in vc without me?",
                "who's in vc rn",
                f"{member.display_name} in vc? interesting",
                "i can't join vc rn but carry on",
                "vc at this hour?"
            ]
            await channel.send(random.choice(responses))
            last_event_message_time = time.time()
    # Someone left VC
    elif before.channel is not None and after.channel is None:
        if random.random() < 0.04:  # Reduced from 0.06
            await asyncio.sleep(random.uniform(10, 30))
            responses = ["kicked already? 💀", "vc over?", f"{member.display_name} left vc lol", "rip vc"]
            await channel.send(random.choice(responses))
            last_event_message_time = time.time()

if __name__ == "__main__":
    if TOKEN:
        keep_alive()  # Starts the dummy web server for Render
        
        try:
            bot.run(TOKEN)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                print("\n" + "="*50)
                print("BANNED BY DISCORD (429) - YOUR IP IS BLOCKED")
                print("Please try changing your Render region (e.g. to Frankfurt).")
                print("Sleeping for 2 minutes before exit to prevent restart spam...")
                print("="*50 + "\n")
                time.sleep(120)
            raise e
        except Exception as e:
            print(f"Fatal error: {e}")
    else:
        print("DISCORD_TOKEN not found.")
