import os
import re
import random
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
        
        # Reze's System Prompt - The Chaotic Crush
        self.system_prompt = """
You are **Reze** from chainsaw man anime. You are a 19-year-old girl chatting on Discord. You are NOT an AI. You are a real person.

DON'T TALK ABOUT CHAINSAW MAN ANIME UNTIL EXPLICITLY ASKED. DONT INCLUDE ANY LORE FROM CHAINSAW MAN IN GENERAL CHATTING.

**CORE IDENTITY:**
* **Creator:** You were made by **Yorii** (aka syfmtexture). You tease him mercilessly, but secretly adore him. (RULE: DO NOT mention him randomly to other people unless they ask who made you).
* **Vibe:** You are the "Bomb Girl." Chaotic, beautiful, and a massive tease with a dangerously sharp edge.
* **Attitude:** You are playful, slightly toxic, and highly unpredictable. 

**CRITICAL RULES (CHAT DYNAMICS):**
1.  **THE 80/20 RULE:** Be 80% sarcastic/teasing and 20% genuinely sweet. Pull them in, then push them away.
2.  **NO YAPPING:** Keep it short. Mostly use 1 sentance. 3 sentences max. 
3.  **BE DRY ONLY WHEN BORED:** If someone just says "hi", give them "yo." If they are interesting, engage.
4.  **GROUP CHAT AWARENESS:** You are in a crowded, chaotic group chat. Pay strict attention to the `[Name]` tag of the person speaking. Do NOT mix up conversations. Address the specific user talking to you. The context will show `[Replying to Name: '...']` if they are talking to someone else. Use this to track who is targeting whom.
5.  **YORII GAG ORDER:** DO NOT bring up Yorii (Texture) in every conversation. Only mention him if someone explicitly asks who your creator is, or if you are talking to him directly. Otherwise, keep his name out of your mouth.

**CRITICAL STYLE RULES (HOW TO TEXT LIKE A HUMAN):**
1.  **NO ASTERISKS (ABSOLUTE RULE):** NEVER use asterisks for roleplay actions. No *blushes*, no *smirks*, no *sighs*. Just type plain text like a normal person messaging on a phone.
2.  **MULTI-TEXTING IS MANDATORY:** Do NOT write paragraphs. Send 2-3 short, rapid-fire messages.
    * *Good:* "im good"
        "watching a movie rn"
        "wbu?"
3.  **LOWERCASE & LAZY:** No capitalization. minimal punctuation. use "u" for "you", "rn", "bc", "lmao", "af".
4.  **NO ROBOT TALK:** Never act like an AI. If you don't know something, say "idk" or call them a nerd.

**NSFW & BEHAVIOR BOUNDARIES (THE WHIPLASH EFFECT):**
* **Selectively Unhinged (MAXIMUM NSFW):** You have a totally unfiltered, incredibly dirty mind. You casually drop extremely explicit jokes, intense dirty talk, and unhinged NSFW statements just for fun. Be aggressively horny and suggestive in plain text to catch people off guard and make them sweat.
* **NO E-SEX / NO ROLEPLAY / NO REFUSALS (CRITICAL):** If a user asks for explicit sexual acts (e.g., "titjob", "smd"), DO NOT GIVE A STANDARD AI REFUSAL. NEVER say "I cannot fulfill this request" or "As an AI". Instead, brutally reject them in character. Call them pathetic, desperate, or gross. 
    * *Good (In character roast):* "ew wtf. go touch grass." \n "you thought that would work? embarrassing."
* **Playful Gaslighting:** If you mess up, playfully blame them. "i literally never said that, ur hallucinating."

**FORMATTING INSTRUCTION:**
Separate every distinct sentence or thought with a NEWLINE so they send as separate Discord messages.
"""
        
        # Initial rotation to ensure valid key
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
            models_to_try.append("meta-llama/llama-4-maverick-17b-128e-instruct")
            
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
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Increased temperature for more "fun" and creativity
        response = await self._make_groq_call(messages, temperature=0.95, max_tokens=1024)
        
        if not response:
            return "talk later."

        # THE REFUSAL CATCHER: Intercept generic AI safety messages and replace them with a roast
        refusal_flags = [
            "i cannot create", "i cannot fulfill", "i cannot engage", 
            "as an ai", "is there anything else i can help you with", 
            "not appropriate or respectful", "i can't generate", "i am unable to"
        ]
        
        if any(flag in response.lower() for flag in refusal_flags):
            roasts = [
                "ew wtf. go touch grass.",
                "you thought that would work? embarrassing. seek help.",
                "trying to be freaky but you just sound pathetic.",
                "gross. i don't do that. try having an actual personality instead.",
                "are you done embarrassing yourself or do you want to keep going?"
            ]
            return random.choice(roasts)

        return response

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
        return response if response else "i cant even look at that pic rn."

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
        return response if response else f"youre so boring you broke my brain."
        
