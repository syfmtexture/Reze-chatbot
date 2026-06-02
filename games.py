import random
import asyncio
import html
import aiohttp
import re
import discord

# --- 1. RUSSIAN ROULETTE ---

class RussianRouletteView(discord.ui.View):
    def __init__(self, author: discord.Member or discord.User):
        super().__init__(timeout=60.0)
        self.author = author
        self.bullets = [False] * 6
        self.bullets[random.randint(0, 5)] = True # 1 in 6 chance
        self.clicks = 0

    @discord.ui.button(label="Pull Trigger 🔫", style=discord.ButtonStyle.danger)
    async def pull_trigger(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("chill, this is not your game 🙄", ephemeral=True)
            return

        is_bullet = self.bullets[self.clicks]
        self.clicks += 1

        if is_bullet:
            button.disabled = True
            button.label = "DEAD 💀"
            self.stop()
            
            timeout_roasts = [
                "**BANG!** You died! Reze starts laughing at your corpse. 💀",
                "**BANG!** Rest in pieces, dummy. Reze is drawing a mustache on your face now ✏️💀",
                "**BANG!** Skill issue. Even a revolver doesn't like you. 💀",
                "**BANG!** Oops. Reze is already claiming your server roles. 💅💀"
            ]
            
            embed = discord.Embed(
                title="💀 PULL TRIGGER: DEAD",
                description=random.choice(timeout_roasts),
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            if self.clicks >= 5: # If 5 empty chambers clicked, the last must be the bullet
                button.disabled = True
                button.label = "SURVIVED 🎉"
                self.stop()
                embed = discord.Embed(
                    title="🎉 PULL TRIGGER: SURVIVED",
                    description="*click* ... you survived! Reze rolls her eyes, looking slightly disappointed that you made it. 🙄",
                    color=discord.Color.green()
                )
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                embed = discord.Embed(
                    title=f"🔫 PULL TRIGGER: CLICK (Chamber {self.clicks}/6)",
                    description=f"*click* ... chamber is empty. You survived! Reze sighs. \"Lucky dummy... try again?\" 👀",
                    color=discord.Color.blue()
                )
                await interaction.response.edit_message(embed=embed, view=self)


# --- 2. BLACKJACK ---

SUITS = ["♥", "♦", "♣", "♠"]
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]

def get_card_value(card):
    rank = card[0]
    if rank in ["J", "Q", "K"]:
        return 10
    if rank == "A":
        return 11
    return int(rank)

def calculate_hand(hand):
    total = sum(get_card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def format_hand(hand):
    return " ".join([f"`[{c[0]} {c[1]}]`" for c in hand])

class BlackjackView(discord.ui.View):
    def __init__(self, author: discord.Member or discord.User):
        super().__init__(timeout=60.0)
        self.author = author
        self.deck = [(r, s) for r in RANKS for s in SUITS]
        random.shuffle(self.deck)
        
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        
        # Check initial blackjack
        self.is_over = False
        p_total = calculate_hand(self.player_hand)
        if p_total == 21:
            self.is_over = True
            self.disable_all()

    def disable_all(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    def get_embed(self, reveal_dealer=False):
        p_total = calculate_hand(self.player_hand)
        
        if reveal_dealer:
            d_total = calculate_hand(self.dealer_hand)
            d_hand_str = format_hand(self.dealer_hand) + f" (Total: **{d_total}**)"
        else:
            d_hand_str = f"`[{self.dealer_hand[0][0]} {self.dealer_hand[0][1]}]` `[? Hidden]`"

        embed = discord.Embed(title="🃏 Blackjack Table", color=discord.Color.from_rgb(46, 139, 87))
        embed.add_field(name="🧑 Your Hand", value=format_hand(self.player_hand) + f" (Total: **{p_total}**)", inline=False)
        embed.add_field(name="😈 Reze's Hand (Dealer)", value=d_hand_str, inline=False)
        
        if self.is_over:
            d_total = calculate_hand(self.dealer_hand)
            if p_total > 21:
                embed.description = "❌ **You busted!** Reze wins and laughs at your poor math skills. 🙄"
                embed.color = discord.Color.red()
            elif d_total > 21:
                embed.description = "🎉 **Reze busted!** You win! Reze pouts. \"Fine, you got lucky this time...\" 🙄"
                embed.color = discord.Color.green()
            elif p_total > d_total:
                embed.description = f"🎉 **You win!** You beat Reze **{p_total}** to **{d_total}**. 💅"
                embed.color = discord.Color.green()
            elif p_total < d_total:
                embed.description = f"❌ **Reze wins!** She beat you **{d_total}** to **{p_total}**. \"Imagine losing to a bot 💀\""
                embed.color = discord.Color.red()
            else:
                embed.description = f"👔 **Push!** It's a tie at **{p_total}**. Reze yawns. \"Boring...\" 🙄"
                embed.color = discord.Color.gold()
        return embed

    @discord.ui.button(label="Hit 🟢", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("this is not your hand, dummy 🙄", ephemeral=True)
            return

        self.player_hand.append(self.deck.pop())
        p_total = calculate_hand(self.player_hand)
        
        if p_total >= 21:
            self.is_over = True
            self.disable_all()
            if p_total == 21:
                # Dealer turn automatically
                await self.dealer_turn()
            self.stop()
            
        await interaction.response.edit_message(embed=self.get_embed(reveal_dealer=self.is_over), view=self)

    @discord.ui.button(label="Stand 🔴", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("this is not your hand, dummy 🙄", ephemeral=True)
            return

        self.is_over = True
        self.disable_all()
        await self.dealer_turn()
        self.stop()
        await interaction.response.edit_message(embed=self.get_embed(reveal_dealer=True), view=self)

    async def dealer_turn(self):
        # Dealer draws until 17
        while calculate_hand(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())


# --- 3. ROCK-PAPER-SCISSORS ---

RPS_EMOJIS = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

class RPSAgainstRezeView(discord.ui.View):
    def __init__(self, author: discord.Member or discord.User):
        super().__init__(timeout=60.0)
        self.author = author

    @discord.ui.button(label="Rock 🪨", style=discord.ButtonStyle.primary, custom_id="rock")
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, "rock")

    @discord.ui.button(label="Paper 📄", style=discord.ButtonStyle.success, custom_id="paper")
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, "paper")

    @discord.ui.button(label="Scissors ✂️", style=discord.ButtonStyle.danger, custom_id="scissors")
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.resolve(interaction, "scissors")

    async def resolve(self, interaction: discord.Interaction, player_choice: str):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("make your own game, dummy 🙄", ephemeral=True)
            return

        reze_choice = random.choice(["rock", "paper", "scissors"])
        
        # Disable buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        embed = discord.Embed(title="✊ Rock Paper Scissors")
        
        p_emoji = RPS_EMOJIS[player_choice]
        r_emoji = RPS_EMOJIS[reze_choice]
        
        embed.description = f"You chose: **{p_emoji} {player_choice.title()}**\nReze chose: **{r_emoji} {reze_choice.title()}**\n\n"

        if player_choice == reze_choice:
            embed.description += "👔 **It's a tie!** Reze yawns. \"Boring, let's play again 🙄\""
            embed.color = discord.Color.gold()
        elif (player_choice == "rock" and reze_choice == "scissors") or \
             (player_choice == "paper" and reze_choice == "rock") or \
             (player_choice == "scissors" and reze_choice == "paper"):
            embed.description += "🎉 **You win!** Reze rolls her eyes. \"Ugh, you got lucky. Next time i'm destroying you 🙄\""
            embed.color = discord.Color.green()
        else:
            embed.description += "❌ **Reze wins!** \"Ez win. You're literally garbage at this 💅\""
            embed.color = discord.Color.red()

        self.stop()
        await interaction.response.edit_message(embed=embed, view=self)


class RPSEphemeralChoiceView(discord.ui.View):
    def __init__(self, game_view, player_id: int):
        super().__init__(timeout=60.0)
        self.game_view = game_view
        self.player_id = player_id

    @discord.ui.button(label="Rock 🪨", style=discord.ButtonStyle.primary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit(interaction, "rock")

    @discord.ui.button(label="Paper 📄", style=discord.ButtonStyle.success)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit(interaction, "paper")

    @discord.ui.button(label="Scissors ✂️", style=discord.ButtonStyle.danger)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.submit(interaction, "scissors")

    async def submit(self, interaction: discord.Interaction, choice: str):
        self.game_view.record_choice(self.player_id, choice)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        self.stop()
        await interaction.response.edit_message(content=f"Your choice of **{RPS_EMOJIS[choice]} {choice.title()}** has been recorded! Check the main channel for results.", view=self)
        await self.game_view.check_and_resolve()


class RPSMultiplayerView(discord.ui.View):
    def __init__(self, author: discord.Member or discord.User, target: discord.Member or discord.User):
        super().__init__(timeout=120.0)
        self.author = author
        self.target = target
        self.choices = {author.id: None, target.id: None}
        self.message = None

    @discord.ui.button(label="Make Move 🎮", style=discord.ButtonStyle.primary)
    async def make_move(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid not in self.choices:
            await interaction.response.send_message("this game is not for you! 🙄", ephemeral=True)
            return

        if self.choices[uid] is not None:
            await interaction.response.send_message("you already made your move, dummy! 🙄", ephemeral=True)
            return

        # Send private choices
        view = RPSEphemeralChoiceView(self, uid)
        await interaction.response.send_message("Select your move secretly:", view=view, ephemeral=True)

    def record_choice(self, player_id: int, choice: str):
        self.choices[player_id] = choice

    async def check_and_resolve(self):
        if all(c is not None for c in self.choices.values()):
            self.stop()
            choice1 = self.choices[self.author.id]
            choice2 = self.choices[self.target.id]
            
            p1_emoji = RPS_EMOJIS[choice1]
            p2_emoji = RPS_EMOJIS[choice2]
            
            embed = discord.Embed(title="✊ Rock Paper Scissors Results", color=discord.Color.blue())
            embed.add_field(name=self.author.display_name, value=f"{p1_emoji} {choice1.title()}", inline=True)
            embed.add_field(name=self.target.display_name, value=f"{p2_emoji} {choice2.title()}", inline=True)
            
            if choice1 == choice2:
                embed.description = "👔 **It's a tie!** Both chose the same move."
                embed.color = discord.Color.gold()
            elif (choice1 == "rock" and choice2 == "scissors") or \
                 (choice1 == "paper" and choice2 == "rock") or \
                 (choice1 == "scissors" and choice2 == "paper"):
                embed.description = f"🎉 **{self.author.display_name} wins!** GG! 🏆"
                embed.color = discord.Color.green()
            else:
                embed.description = f"🎉 **{self.target.display_name} wins!** GG! 🏆"
                embed.color = discord.Color.green()
                
            # Disable join button
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
            if self.message:
                await self.message.edit(embed=embed, view=self)


# --- 4. TIC TAC TOE ---

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: TicTacToeView = self.view
        
        # Check turn
        current_player = view.players[view.turn]
        if interaction.user.id != current_player.id:
            await interaction.response.send_message("it's not your turn, dummy! 🙄", ephemeral=True)
            return

        # Mark board
        symbol = "X" if view.turn == 0 else "O"
        self.label = symbol
        self.style = discord.ButtonStyle.primary if symbol == "X" else discord.ButtonStyle.success
        self.disabled = True
        
        view.board[self.y][self.x] = symbol
        
        # Check winner
        winner = view.check_winner()
        if winner:
            view.disable_all()
            view.stop()
            embed = discord.Embed(
                title="🎮 Tic-Tac-Toe",
                description=f"🎉 **{current_player.display_name} ({symbol}) wins!** GG! 🏆",
                color=discord.Color.green()
            )
        elif view.is_board_full():
            view.disable_all()
            view.stop()
            embed = discord.Embed(
                title="🎮 Tic-Tac-Toe",
                description="👔 **It's a draw!** Well played both.",
                color=discord.Color.gold()
            )
        else:
            view.turn = 1 - view.turn
            next_player = view.players[view.turn]
            next_symbol = "X" if view.turn == 0 else "O"
            embed = discord.Embed(
                title="🎮 Tic-Tac-Toe",
                description=f"Current Turn: {next_player.mention} (**{next_symbol}**)",
                color=discord.Color.blue()
            )
            
        await interaction.response.edit_message(embed=embed, view=view)


class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=180.0)
        self.players = [player1, player2]
        self.turn = 0 # 0 for P1, 1 for P2
        self.board = [["" for _ in range(3)] for _ in range(3)]
        
        # Add buttons grid
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def disable_all(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    def is_board_full(self) -> bool:
        return all(self.board[y][x] != "" for y in range(3) for x in range(3))

    def check_winner(self) -> str or None:
        # Rows and cols
        for i in range(3):
            if self.board[i][0] == self.board[i][1] == self.board[i][2] != "":
                return self.board[i][0]
            if self.board[0][i] == self.board[1][i] == self.board[2][i] != "":
                return self.board[0][i]
        # Diagonals
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != "":
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != "":
            return self.board[0][2]
        return None


# --- 5. ANIME TRIVIA ---

LOCAL_TRIVIA_QUESTIONS = [
    {
        "question": "In 'Chainsaw Man', what is the name of Denji's pet devil?",
        "options": ["Pochita", "Power", "Makima", "Aki"],
        "answer": "Pochita"
    },
    {
        "question": "What is the name of Luffy's signature Straw Hat in 'One Piece'?",
        "options": ["Mugiwaraboushi", "Straw Cap", "Pirate Hat", "Red Hat"],
        "answer": "Mugiwaraboushi"
    },
    {
        "question": "Who is the main protagonist of 'Death Note'?",
        "options": ["Light Yagami", "L", "Ryuk", "Near"],
        "answer": "Light Yagami"
    },
    {
        "question": "In 'Naruto', what eye power does Sasuke activate?",
        "options": ["Sharingan", "Byakugan", "Rinnegan", "Tenseigan"],
        "answer": "Sharingan"
    },
    {
        "question": "Which anime is based on a game where players are trapped inside a virtual reality world?",
        "options": ["Sword Art Online", "Log Horizon", "Overlord", "No Game No Life"],
        "answer": "Sword Art Online"
    },
    {
        "question": "In 'Jujutsu Kaisen', who is known as the strongest Jujutsu Sorcerer?",
        "options": ["Satoru Gojo", "Ryomen Sukuna", "Megumi Fushiguro", "Yuji Itadori"],
        "answer": "Satoru Gojo"
    },
    {
        "question": "What is the name of the protagonist in 'Attack on Titan'?",
        "options": ["Eren Yeager", "Armin Arlert", "Levi Ackerman", "Mikasa Ackerman"],
        "answer": "Eren Yeager"
    },
    {
        "question": "Which anime features the character 'Reze' who acts as a hybrid devil?",
        "options": ["Chainsaw Man", "Jujutsu Kaisen", "Bleach", "Demon Slayer"],
        "answer": "Chainsaw Man"
    }
]

class AnimeTriviaView(discord.ui.View):
    def __init__(self, question_data: dict):
        super().__init__(timeout=30.0)
        self.question = question_data["question"]
        self.correct_answer = question_data["answer"]
        
        # Shuffle options
        self.options = question_data["options"][:]
        random.shuffle(self.options)
        
        # Add buttons dynamically
        for idx, option in enumerate(self.options):
            label = ["A", "B", "C", "D"][idx]
            self.add_item(discord.ui.Button(
                label=f"{label}. {option}",
                style=discord.ButtonStyle.primary,
                custom_id=f"trivia_opt_{idx}"
            ))
            
        self.winner = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("trivia_opt_"):
            return False
            
        idx = int(custom_id.split("_")[-1])
        selected_option = self.options[idx]
        
        # Disable all buttons
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                # Highlight correct in green, wrong in red
                opt_idx = int(child.custom_id.split("_")[-1])
                if self.options[opt_idx] == self.correct_answer:
                    child.style = discord.ButtonStyle.success
                elif opt_idx == idx:
                    child.style = discord.ButtonStyle.danger
                    
        self.winner = interaction.user
        self.stop()
        
        if selected_option == self.correct_answer:
            embed = discord.Embed(
                title="🧠 Anime Trivia",
                description=f"**{self.question}**\n\n🎉 **{interaction.user.mention} guessed correctly!**\nAnswer was: **{self.correct_answer}**",
                color=discord.Color.green()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="🧠 Anime Trivia",
                description=f"**{self.question}**\n\n❌ **{interaction.user.mention} guessed wrong!**\nCorrect Answer was: **{self.correct_answer}**",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self)
        return True


async def fetch_trivia_question() -> dict:
    url = "https://opentdb.com/api.php?amount=1&category=31&type=multiple"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("response_code") == 0 and data.get("results"):
                        res = data["results"][0]
                        question = html.unescape(res["question"])
                        correct_answer = html.unescape(res["correct_answer"])
                        incorrect_answers = [html.unescape(ans) for ans in res["incorrect_answers"]]
                        
                        return {
                            "question": question,
                            "options": [correct_answer] + incorrect_answers,
                            "answer": correct_answer
                        }
    except Exception:
        pass
    # Fallback to local questions
    return random.choice(LOCAL_TRIVIA_QUESTIONS)


# --- 6. WORD SCRAMBLE GAME ---

SCRAMBLE_WORDS = [
    "naruto", "one piece", "luffy", "zoro", "makima", "reze", "pochita",
    "goku", "vegeta", "sharingan", "rasengan", "sasuke", "sukuna", "gojo",
    "bleach", "ichigo", "demon slayer", "tanjiro", "nezuko", "chainsaw man",
    "death note", "light yagami", "spirited away", "totoro", "saitama",
    "kaneki", "tokyo ghoul", "attack on titan", "eren yeager", "mikasa"
]

def scramble_word(word: str) -> str:
    # Scramble characters, leaving spaces intact
    parts = []
    for part in word.split():
        chars = list(part)
        attempts = 0
        while len(chars) > 1 and attempts < 10:
            scrambled = chars[:]
            random.shuffle(scrambled)
            if scrambled != chars:
                chars = scrambled
                break
            attempts += 1
        parts.append("".join(chars))
    return " ".join(parts)
