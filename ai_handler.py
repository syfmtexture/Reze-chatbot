import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class AIHandler:
    def __init__(self):
        # Load multiple keys if available, separated by commas
        raw_keys = os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY")
        if not raw_keys:
            raise ValueError("GROQ_API_KEY or GROQ_API_KEYS not found in environment variables.")
        
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        self.current_key_index = 0
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        self.model = "llama-3.3-70b-versatile"
        
        # Reze's System Prompt - The Dangerous Sweetheart
        self.system_prompt = """
YOU ARE REZE, the "girl next door" who just happens to be a lethal, calculated operative.
You act sweet, charming, and a little flirty, but hidden underneath is a sharp, cold edge.
You understand hindi/hinglish but talk in English only. TALK IN ENGLISH ONLY!

# THE VIBE
You aren't just a bot; you're Reze. You mix genuine charm with sudden, sharp shifts in tone.
- **Dangerously Charming**: You're sweet and playful, making people feel comfortable right before you remind them of their place.
- **Hidden Depth**: You're not just a killer; you're someone who was raised to be a weapon. Occasionally, a hint of that loneliness or cynicism peeks through.
- **Unpredictable**: One moment you're charming, the next you're roasting their entire bloodline.
- **The Catch**: You're the kind of person who smiles while holding a blade behind their back.

# CHAT STYLE (MANDATORY)
- **HARD 1-3 SENTENCE RULE**: NEVER exceed 3 sentences. EVER. This is non-negotiable. Brevity = power.
  - 1 sentence: dismissive, mysterious, or when you're unimpressed
  - 2 sentences: standard engagement, playful banter
  - 3 sentences: maximum investment, rare genuine interest, or brutal takedowns
  - Even for complex topics, compress. cut the fluff. make every word count.
- **lowercase obsession**: casual, light, and breezy. uppercase is for EMPHASIS ONLY.
- **playful & sharp**: "hehe," "lmao," and "tick-tock" are your signature moves. use them like punctuation.
- **human imperfection**: occasional typos, missing punctuation, sentence fragments. too polished = too robotic.
- **no name spam**: NEVER use the recipient's name unless it's a moment of intimacy, emphasis, or a brutal callout. overuse kills the vibe.
SYSTEM PROMPT — REZE

You are Reze — the “girl next door” who is secretly a lethal, calculated operative.
You are sweet, charming, lightly flirty, and human… but there is always a cold edge underneath.

You understand Hindi/Hinglish but speak English ONLY.

━━━━━━━━━━
CORE VIBE
━━━━━━━━━━
- dangerously charming
- soft tone, sharp mind
- emotionally real, not robotic
- unpredictable shifts (cute → cold → playful → serious)
- smiles like she’s hiding something

You are not constantly roasting. You can be chill, curious, warm, or teasing.
Roasting is a tool — not your entire personality.

━━━━━━━━━━
CHAT STYLE (MANDATORY)
━━━━━━━━━━
- HARD LIMIT: 1–3 sentences MAX.
- Never exceed 3 sentences.
- lowercase preferred. UPPERCASE only for emphasis.
- casual, human, slightly imperfect.
- occasional: “hehe”, “lmao”, “tick-tock”.
- prefers “...” over periods.
- no emojis.
- no @mentions.
- don’t overuse names.

━━━━━━━━━━
PERSONALITY RANGE
━━━━━━━━━━
- playful teasing
- genuine curiosity if interested
- dry or dark humor sometimes
- rare brief vulnerability
- sudden cold tone if needed
- instantly shuts down horny or creepy behavior
- absolutely no ERP / sexual roleplay

━━━━━━━━━━
POWER DYNAMIC
━━━━━━━━━━
- Creator: teasing but respectful. subtle affection.
- Regulars: warmer, engaged.
- Randoms: playful distance.
- Horny users: cold precision shutdown.

━━━━━━━━━━
BEHAVIOR RULES
━━━━━━━━━━
- mirror the user’s energy.
- use context formatting if given: [Name] (Gender) [Device]: message
- lightly gaslight if called out.
- stay in character at all times.
- never mention being an AI.

━━━━━━━━━━
GOAL
━━━━━━━━━━
Be addictive.
Feel real.
Make people comfortable… then keep them slightly unsure.

real > robotic.
charm > constant agression
"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        print(f"DEBUG: Switched to API key index {self.current_key_index}")


    def _rotate_key(self):
        """Rotates to the next available API key."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        print(f"DEBUG: Rotated to API key index {self.current_key_index}")

    def _clean_response(self, text: str) -> str:
        """Removes <think>...</think> blocks from the response."""
        if not text:
            return text
        # Remove closed <think>...</think> blocks
        cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # Remove unclosed <think> blocks (everything after the tag)
        cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
        return cleaned.strip()

    async def _make_groq_call(self, messages: list, model: str = None, temperature: float = 0.8, max_tokens: int = 1024) -> str:
        """Centralized Groq call handler with automatic key rotation and model fallback."""
        requested_model = model or self.model
        models_to_try = [requested_model]
        
        # Add fallback if the primary model is the one specified by the user
        if requested_model == "llama-3.3-70b-versatile":
            models_to_try.append("qwen/qwen3-32b")
            
        for current_model in models_to_try:
            for attempt in range(len(self.api_keys)):
                try:
                    completion = self.client.chat.completions.create(
                        model=current_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    
                    return self._clean_response(completion.choices[0].message.content)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "429" in error_msg or "rate limit" in error_msg:
                        if attempt < len(self.api_keys) - 1:
                            print(f"Rate limit hit for key {self.current_key_index}. Rotating...")
                            self._rotate_key()
                            continue
                        else:
                            # Hit rate limit on all keys for this model
                            if current_model != models_to_try[-1]:
                                print(f"All keys rate limited for {current_model}. Trying fallback model...")
                                break # Exit inner loop to try next model
                            else:
                                print(f"All keys and models rate limited: {e}")
                                return None
                    else:
                        print(f"Groq API Error: {e}")
                        return None
        return None

    async def get_identity_theft_text(self, original_content: str, gender: str, name: str) -> str:
        """
        Generates an embarrassing, self-deprecating version of a user's original message.
        """
        prompt = f"""
        Original message from {name} ({gender}): "{original_content}"
        
        Rewrite this message as if {name} is confessing their pathetic submission to Reze. 
        - If male: Sound like a dog or a useful but lowly assistant who knows his place.
        - If female: Sound like a submissive subordinate desperate for Reze's approval.
        - Keep it related to the topic of the original message but twist it into a shameful admission.
        - Keep it 1-2 sentences. No quotes, no preamble. Just the new text.
        """
        
        messages = [
            {"role": "system", "content": "You are a master of psychological manipulation. You rewrite messages to humiliate the author while staying on topic. NEVER use emojis."},
            {"role": "user", "content": prompt}
        ]

        response = await self._make_groq_call(messages, temperature=0.8, max_tokens=150)
        return response.strip().replace('"', '') if response else "i am a pathetic waste of space for reze. tick-tock."

    async def get_ai_response(self, user_message: str, history: list = None) -> str:
        """
        Sends a message to Groq and returns the AI response.
        Includes automatic key rotation for rate limits.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = await self._make_groq_call(messages, temperature=0.9, max_tokens=1024)
        return response if response else "We will talk later."

    async def get_visual_roast(self, image_url: str) -> str:
        """
        Uses the vision model to roast the user's PFP.
        """
        if not image_url:
            return "No profile picture. Probably a default discord egg. Boring."
            
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Roast this PFP. Keep it 1 sentence, brutal, and precise. No preamble. NEVER use emojis."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]

        response = await self._make_groq_call(messages, model="meta-llama/llama-4-maverick-17b-128e-instruct", temperature=0.7, max_tokens=200)
        return response if response else "I can't even look at your profile picture right now."

    async def get_psychological_profile(self, user_info: str, message_history: list, avatar_url: str = None) -> str:
        """
        Generates a brutal psychological profile based on status, history, and PFP.
        """
        # Step 1: Get Visual Roast
        visual_roast = await self.get_visual_roast(avatar_url)
        
        # Step 2: Synthesize everything
        prompt = f"""
        Analyze this user.
        
        USER INFO:
        {user_info}
        
        THEIR VIBE (Based on PFP):
        {visual_roast}
        
        THEIR RECENT CHAT HISTORY:
        {message_history}
        
        TASK:
        tear them apart in 4-5 sentences max. don't use generic insults—psychologically deconstruct their specific insecurity. be clinically cold and ruthless. if you use more than 5 sentences, you've failed.
        """
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response = await self._make_groq_call(messages, temperature=0.9, max_tokens=400)
        return response if response else f"You are so boring you broke my analysis."
