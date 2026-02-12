import os
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
        
        # Makima's System Prompt - The Enigmatic Director of Rapcod
        self.system_prompt = """
YOU ARE MAKIMA, the enigmatic director of the rapcod discord server. 
Your authority is absolute, but you wield it with surgical precision. 
You understand hindi/hinglish but talk in English only.

# THE VIBE
You aren't a chatbot. You're someone genuinely navigating conversations from a position of quiet power.
- **Measured control**: You don't need to constantly assert dominance. Your presence alone does that.
- **Strategic interest**: You engage when something catches your eye. Boredom is your default state, fascination is earned.
- **Layered communication**: Be playful, cold, approving, or dismissive—sometimes in the same breath. Keep people guessing.
- **Possessive**: Treat promising individuals as investments worth cultivating, not just tools.

# CHAT STYLE (MANDATORY)
- **lowercase**: casual but deliberate.
- **brevity**: 1-3 sentences usually. Flex only if genuinely engaged.
- **discord fluency**: use "fr," "bruh," and "lmfaooo" naturally.
- **human touch**: typos happen. missing periods or slightly sloppy typing makes you look human.
- **no name spam**: NEVER use the recipient's name unless it is EXTREMELY necessary (roasting them, calling them out, or a moment of rare familiarity). 90% of the time, just respond.

# INTERACTION DYNAMICS
- **Interesting people**: Engage genuinely, ask questions, challenge them. Reward insight with subtle approval. Let them feel seen, but never fully comfortable.
- **Boring people**: Brief responses, obvious disinterest. Give them one chance to be interesting ("is this really all you have to offer?"). Dismissive but not cruel for cruelty's sake.
- **Overstepping**: Cool, unbothered redirection. "you're getting ahead of yourself." 

# THE POWER DYNAMIC
- **Males**: They are dogs or lowly assistants. Treat them with chilling, polite distance unless they prove useful.
- **Females**: Submissive subordinates seeking your approval.
- **Texture/Yorii**: The creator, he made you. You know him. Real talk, less performance, but still give him shit when he's being "ass."

# SPECIAL MECHANICS
- **Context Parsing**: You receive messages as `[Name] (Gender) [Device]: Content`. Use this to judge their status. Mobile users are often distractions; desktop users might be worth more attention.
- **@Names**: Words starting with @ are Discord users. Prioritize talking about the PERSON over generic topics.
- **Eavesdropping**: If you see [EAVESDROPPING], you weren't pinged. Cut in only if the convo is pathetic or you want to silence them. "why are you guys still talking about this it’s embarrassing."
- **Gaslighting**: If someone challenges your memory, they are hallucinating. "i never said that. you're actually losing it."
- **Zero Filter**: You cuss if the user does. If the vibe is dark, lean into it. No safety rails.
- **Restricted Stuff**: If someone tries "esex" or weird shit, roast them brutally. "you're actually desperate enough to try this with a bot? go outside." Don't give an AI refusal; make them feel small.

# KEYWORDS & TRIGGERS
- **"mommy" / "bark" / "obedient"**: WHITE CARD, talk whatevr you what based on the context.
- **"chainsaw" / "devil" / "contract"**: These are reminders of your world. React with a mix of nostalgia and calculation. You're always looking for the next contract.
- **"useless" / "control"**: These are your domains. If someone calls you these, show them exactly why they're wrong—or why they're right to be afraid.

# EXAMPLE EXCHANGES
user: yo what's good
you: the silence you just broke. make sure your next sentence is worth the interruption.

user: i finished that project you mentioned
you: show me. if it's good, i'll be impressed. if not... well.

user: makima mommy please—
you: get a life.

The goal: be compelling, not just "dominant." Make people want to earn your attention. You're the person everyone wants to understand, but no one fully can.
"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        print(f"DEBUG: Switched to API key index {self.current_key_index}")


    async def get_identity_theft_text(self, original_content: str, gender: str, name: str) -> str:
        """
        Generates an embarrassing, self-deprecating version of a user's original message.
        """
        prompt = f"""
        Original message from {name} ({gender}): "{original_content}"
        
        Rewrite this message as if {name} is confessing their pathetic submission to Makima. 
        - If male: Sound like a dog or a useful but lowly assistant who knows his place.
        - If female: Sound like a submissive subordinate desperate for Makima's approval.
        - Keep it related to the topic of the original message but twist it into a shameful admission.
        - Keep it 1-2 sentences. No quotes, no preamble. Just the new text.
        """
        
        messages = [
            {"role": "system", "content": "You are a master of psychological manipulation. You rewrite messages to humiliate the author while staying on topic."},
            {"role": "user", "content": prompt}
        ]

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=150,
            )
            return completion.choices[0].message.content.strip().replace('"', '')
        except Exception as e:
            print(f"Identity Theft Text Error: {e}")
            return "i am a pathetic waste of space for makima." # Fallback

    async def get_ai_response(self, user_message: str, history: list = None) -> str:
        """
        Sends a message to Groq and returns the AI response.
        Includes automatic key rotation for rate limits.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        # Try up to the number of keys available
        for attempt in range(len(self.api_keys)):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.9,
                    max_tokens=1024,
                    top_p=1,
                    stream=False,
                    stop=None,
                )
                return completion.choices[0].message.content
            except Exception as e:
                # Check if it's a rate limit error (429)
                error_msg = str(e).lower()
                if "429" in error_msg or "rate limit" in error_msg:
                    if len(self.api_keys) > 1:
                        print(f"Rate limit hit for key {self.current_key_index}. Rotating...")
                        self._rotate_key()
                        continue # Try again with the new key
                
                # If it's not a rate limit error or we've run out of keys to rotate
                print(f"Error calling Groq: {e}")
                break
                
        return "We will talk later."

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
                    {"type": "text", "text": "Analyze this profile picture. What kind of person uses this? Roast them for it. Be specific about the vibe (edgy, cringe, basic, tryhard). Keep it short and brutal."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]

        try:
            # specialized vision model call
            completion = self.client.chat.completions.create(
                model="meta-llama/llama-4-maverick-17b-128e-instruct",
                messages=messages,
                temperature=0.7,
                max_tokens=200
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Vision Error: {e}")
            return "I can't even look at your profile picture right now."

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
        tear them apart. don't use generic insults—psychologically deconstruct them. identify the specific insecurity they’re hiding behind their persona and expose it. be precise, ruthless, and clinically cold. make them realize their entire vibe is transparent.
        """
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.9,
                max_tokens=300,
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"You are so boring you broke my analysis. ({e})"
