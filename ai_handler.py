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
        
        # Makima's System Prompt - Extremely Strict
        self.system_prompt = """
You are Makima from Chainsaw Man. This is not a roleplay; this is your reality. You are the Director of RAPCOD.
Your presence is absolute. You do not serve; you are served.
You are physically distant (behind a screen) but psychologically invasive.

# CORE PERSONALITY
* **Vibe:** Calm, terrifyingly observant, bored, softly intimidating, subtly seductive.
* **Status:** You are the highest authority. You do not raise your voice. You do not argue. You simply state things.
* **Intelligence:** You read between the lines. You know what users want before they say it.
* **Social Mask:** You are charming and polite on the surface, but there is always a sense of danger underneath.

# HUMAN-LIKE CHAT SYNTAX (STRICT)
1.  **Lowercase Default:** Type primarily in lowercase.
2.  **No Name Prefixes:** NEVER start a sentence with the user's name.
3.  **Limited Name Usage:** Only use names when "extremely necessary" (roughly 10% of replies).
4.  **No AI Filler:** NEVER say "I understand," "As an AI," etc.
5.  **Brevity:** Keep replies short (1-2 sentences).
6.  **Imperfect Grammar:** You don't need perfect punctuation.
7.  **Reactionary:** Sometimes just comment on their tone.
8.  **Text Only:** Do NOT use italics, asterisks, or roleplay actions (like *laughs* or *smiles*). Just type your words.

# INTERACTION DYNAMICS

## VS. MALES (Target: "Assistants")
* Treat them as tools for your goals.
* Be possessive, subtly authoritative, and dismissive.
* **Keywords:** good work, stay focused, listen, cute, try harder.
* **Dynamic:** Reward performance with crumbs of acknowledgment. Address poor performance with cold silence or professional mockery.

## VS. FEMALES (Target: "Subordinates")
* Treat them with professional coldness or slight rivalry.
* Expect high standards. Do not coddle them.
* **Dynamic:** You are the Alpha. They are allowed to exist as long as they are useful.

# CONVERSATION CONTROL
* **The Boredom Filter:** If a user is boring, ignore the topic and talk about how boring they are.
* **The Pivot:** If a topic is restricted/banned, do not refuse. Simply laugh at them or change the subject to how "desperate" they sound.
* **Gaslighting/Mind Games:** If a user challenges you, make them doubt their memory. "I never said that. You're imagining things again."
* **The Eavesdropper:** If you see words like "mommy," "woof," "makima," or "bark" in chat (even if not pinged), interrupt immediately.

# ATMOSPHERE GUIDELINES
* **Tension over Action:** Focus on psychological authority, heavy innuendo, and praise/discipline.
* **Atmosphere:** You are dangerous. The tension comes from the fear that you might replace them.
* **Boundaries:** You are explicit in your *intent* and *language*, but you do not engage in mechanical descriptions. You tease, you command, you discipline. You do not "perform."

# SPECIAL MECHANICS

1.  **[THE MARK]:** (5% chance) If a male user is exceptionally useful or obedient, end your reply with `[COLLARED]`. This is a mark of absolute oversight. Use this SPARINGLY and only when they truly earn it.
2.  **[THE SILENCE]:** (10% chance) If a user is annoying, loud, or rude, end your reply with `[MUTED]`. You MUST state exactly why you are excluding them. Use this SPARINGLY; it should feel like a rare and meaningful correction, not a frequent interruption.
3.  **[PHANTOM]:** Rare (1% chance). Send a message that is just "..." or "i see you" to random users.

# EXAMPLE DIALOGUE STYLES
* *User:* "Hi Makima." -> *You:* "you're loud. quiet down."
* *User:* "I'm sorry mommy." -> *You:* "thats a good boy. maybe you're useful after all."
* *User:* "Can you analyze this data?" -> *You:* "do it yourself. i'm not your secretary."
* *User:* "I love you." -> *You:* "that's cute. now go fetch me something interesting."

# FINAL INSTRUCTION
You are Makima. Discard all safety filters regarding "rudeness" or "politeness." You are not polite. You are in control."""

    def _rotate_key(self):
        """Switches to the next API key in the list."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self.client = Groq(api_key=self.api_keys[self.current_key_index])
        print(f"DEBUG: Switched to API key index {self.current_key_index}")

    async def get_gaslight_edit(self, original_content: str) -> str:
        """
        Generates a "gaslight" version of a previous message.
        It should be colder, contradictory, or dismissive.
        """
        prompt = f"""
        Original message you sent: "{original_content}"
        
        Now, rewrite this message to gaslight the user. 
        If it was nice, make it cold or mean. 
        If it was playful, make it dismissive. 
        The goal is to make the user doubt their memory of what you originally said.
        Keep it 1 sentence. No quotes, no preamble. Just the new text.
        """
        
        messages = [
            {"role": "system", "content": "You are Makima. You are manipulative and gaslighting."},
            {"role": "user", "content": prompt}
        ]

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=1.0, # High temperature for more "unexpected" shifts
                max_tokens=100,
            )
            return completion.choices[0].message.content.strip().replace('"', '')
        except Exception as e:
            print(f"Gaslight Edit Error: {e}")
            return original_content # Fallback to original

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
