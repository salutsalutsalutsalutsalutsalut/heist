import discord
from discord import app_commands, Interaction, ButtonStyle
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from utils import default, permissions
from utils.db import redis_client
from utils.embed import cembed
from utils.error import error_handler
from dotenv import dotenv_values
import datetime
import random, aiohttp, io, pytz, time, datetime, secrets, asyncio, os, aiohttp, urllib.parse, re, json, asyncio, aiofiles

footer = "heist.lol"

async def load_custom_words():
    async with aiofiles.open('/heist/words.json', mode='r') as f:
        contents = await f.read()
        return json.loads(contents)

class TypeRacerButton(Button):
    def __init__(self, label, custom_id, style=discord.ButtonStyle.success):
        super().__init__(style=style, label=label, custom_id=custom_id)

    async def callback(self, interaction):
        view = self.view
        if interaction.user != view.initiating_user:
            await interaction.response.send_message("You aren't participating in this game.", ephemeral=True)
        else:
            await view.start_race(interaction)

class TypeRacerModal(Modal, title="Type Racer"):
    def __init__(self, words):
        super().__init__()
        self.words = words
        self.start_time = time.time()

        placeholder_text = " ".join(self.words)
        if len(placeholder_text) > 100:
            placeholder_text = placeholder_text[:97] + "..."

        self.add_item(TextInput(
            label="Text (Don't type here)",
            style=discord.TextStyle.paragraph,
            placeholder=placeholder_text,
            required=False,
            custom_id="displayed_text"
        ))

        self.typing_input = TextInput(
            label="Type HERE",
            style=discord.TextStyle.paragraph,
            placeholder="Type the above text here...",
            required=True,
            custom_id="typing_input"
        )
        self.add_item(self.typing_input)

    async def on_submit(self, interaction):
        end_time = time.time()
        typing_time = end_time - self.start_time

        typed_words = self.typing_input.value.strip().split()
        words_typed = len(typed_words)
        minutes_taken = typing_time / 60

        if minutes_taken > 0:
            words_per_minute = words_typed / minutes_taken
        else:
            words_per_minute = 0

        correct_words = sum(1 for i, word in enumerate(typed_words) if i < len(self.words) and word == self.words[i])
        accuracy = (correct_words / len(self.words)) * 100

        if accuracy < 50:
            embed = await cembed(
                interaction,
                title="🏁 Type Race Failed! 🏁",
                description=f"You failed in `{typing_time:.3f}` seconds!\nFor a WPM of `{words_per_minute:.2f}` and an accuracy of `{accuracy:.2f}%`!\nYour accuracy was too low to win the game! (<50%)",
            )
            embed.add_field(name="Text:", value=f"```{' '.join(self.words)}```", inline=False)
            embed.add_field(name="You typed:", value=f"```{self.typing_input.value}```", inline=False)
        else:
            embed = await cembed(
                interaction,
                title="Type Race Finished!",
                description=f"You finished in `{typing_time:.3f}` seconds!\nFor a WPM of `{words_per_minute:.2f}` and an accuracy of `{accuracy:.2f}%`!",
            )
            embed.add_field(name="Text:", value=f"```{' '.join(self.words)}```", inline=False)
            embed.add_field(name="You typed:", value=f"```{self.typing_input.value}```", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)

class TypeRacerView(View):
    def __init__(self, initiating_user):
        super().__init__(timeout=300)
        self.initiating_user = initiating_user
        self.add_item(TypeRacerButton("Start Race", "start_race"))

    async def start_race(self, interaction):
        CUSTOM_WORDS = await load_custom_words()
        words = random.sample(CUSTOM_WORDS, 10)
        modal = TypeRacerModal(words)
        await interaction.response.send_modal(modal)

# class BlackjackAcceptButton(Button):
#     def __init__(self, author: discord.Member):
#         super().__init__(style=ButtonStyle.green, emoji="<a:vericheckg:1301736918794371094>", custom_id=f"accept_blackjack_{author.id}")
#         self.author = author

#     async def callback(self, interaction: Interaction):
#         try:
#             if interaction.user.id == self.author.id:
#                 await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
#                 return

#             game_id = str(secrets.token_hex(8))
#             view = BlackjackView(self.author, interaction.user, game_id)
#             embed = view.create_game_embed()
#             await interaction.response.edit_message(content=None, embed=embed, view=view)
#         except Exception as e:
#             await error_handler(interaction, e, fallback_message="An error occurred while starting the game.")

# class BlackjackButton(Button):
#     def __init__(self, label: str, custom_id: str, style: ButtonStyle = ButtonStyle.secondary):
#         super().__init__(style=style, label=label, custom_id=custom_id)

#     async def callback(self, interaction: Interaction):
#         view: BlackjackView = self.view
#         await view.handle_action(interaction, self.label.lower())

# class BlackjackView(View):
#     def __init__(self, player1: discord.Member, player2: discord.Member, game_id: str):
#         super().__init__(timeout=500)
#         self.game_id = game_id
#         self.player1 = player1
#         self.player2 = player2
#         self.current_player = player1
#         self.deck = self.create_deck()
#         self.player1_hand = []
#         self.player2_hand = []
#         self.player1_split_hand = None
#         self.player2_split_hand = None
#         self.current_split_hand = None
#         self.player1_stood = False
#         self.player2_stood = False
#         self.deal_initial_cards()

#         self.add_item(BlackjackButton("Hit", f"hit_{game_id}", style=ButtonStyle.primary))
#         self.add_item(BlackjackButton("Stand", f"stand_{game_id}"))
#         self.split_button = BlackjackButton("Split", f"split_{game_id}")
#         self.add_item(self.split_button)

#         self.update_split_button()

#     def create_deck(self):
#         suits = ['c', 'd', 'h', 's']
#         values = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
#         return [f"{v}{s}" for s in suits for v in values]

#     def deal_initial_cards(self):
#         random.shuffle(self.deck)
#         if len(self.deck) < 4:
#             self.deck = self.create_deck()
#             random.shuffle(self.deck)
        
#         while True:
#             self.player1_hand = [self.deck.pop(), self.deck.pop()]
#             if self.calculate_hand_value(self.player1_hand) < 10:
#                 break
#         while True:
#             self.player2_hand = [self.deck.pop(), self.deck.pop()]
#             if self.calculate_hand_value(self.player2_hand) < 10:
#                 break

#     def calculate_hand_value(self, hand):
#         value = 0
#         aces = 0
#         for card in hand:
#             if card[0] in ['J', 'Q', 'K']:
#                 value += 10
#             elif card[0] == 'A':
#                 aces += 1
#             else:
#                 value += int(card[:-1])
        
#         for _ in range(aces):
#             if value + 11 <= 21:
#                 value += 11
#             else:
#                 value += 1
        
#         return value

#     def replenish_deck(self):
#         self.deck = self.create_deck()
#         random.shuffle(self.deck)

#     def update_split_button(self):
#         current_hand = self.current_player_hand()
#         can_split = len(current_hand) == 2 and current_hand[0][:-1] == current_hand[1][:-1]
#         self.split_button.disabled = not can_split

#     def create_game_embed(self):
#         self.update_split_button()
#         embed = discord.Embed(
#             title="Blackjack",
#             description=f"**__{self.current_player.mention}'s turn__**\nChoose your action: Hit, Stand, or Split.",
#             color=0x3b3b3b
#         )

#         def card_to_emoji(card):
#             emoji_id = self.get_emoji_id(card)
#             if emoji_id == '0':
#                 return f"{card}"
#             return f"<:{card}:{emoji_id}>"

#         def hand_to_str(hand):
#             return ' '.join(card_to_emoji(card) for card in hand)

#         player1_cards = hand_to_str(self.player1_hand)
#         player2_cards = hand_to_str(self.player2_hand)

#         embed.add_field(name=f"{self.player1.name}'s hand", value=f"{player1_cards}\n\nScore: {self.calculate_hand_value(self.player1_hand)}", inline=True)
#         embed.add_field(name=f"{self.player2.name}'s hand", value=f"{player2_cards}\n\nScore: {self.calculate_hand_value(self.player2_hand)}", inline=True)

#         if self.player1_split_hand:
#             split_cards = hand_to_str(self.player1_split_hand)
#             embed.add_field(name=f"{self.player1.name}'s split hand", value=f"{split_cards}\n\nScore: {self.calculate_hand_value(self.player1_split_hand)}", inline=True)
        
#         if self.player2_split_hand:
#             split_cards = hand_to_str(self.player2_split_hand)
#             embed.add_field(name=f"{self.player2.name}'s split hand", value=f"{split_cards}\n\nScore: {self.calculate_hand_value(self.player2_split_hand)}", inline=True)

#         embed.set_footer(text="heist.lol", icon_url="https://git.cursi.ng/heist.png?a")

#         return embed

#     def get_emoji_id(self, card):
#         emoji_ids = {
#             'Ac': '1277339621931614431', 'Ad': '1277339638633074829', 'Ah': '1277339670115778613', 'As': '1277339705591201834',
#             '2c': '1277336190890279005', '2d': '1277336210049863762', '2h': '1277336231994327050', '2s': '1277336263481102436',
#             '3c': '1277336370641113148', '3d': '1277336428807717017', '3h': '1277336449221398528', '3s': '1277336467919863828',
#             '4c': '1277336519488700436', '4d': '1277336538308546560', '4h': '1277336555119444020', '4s': '1277336572005580900',
#             '5c': '1277336588891721768', '5d': '1277336615597113384', '5h': '1277336674426294283', '5s': '1277336729522667531',
#             '6c': '1277336776993935464', '6d': '1277336840487174258', '6h': '1277336896527274007', '6s': '1277337048034054305',
#             '7c': '1277337074713755678', '7d': '1277337109761626246', '7h': '1277337138375036979', '7s': '1277339225620086987',
#             '8c': '1277339252891451462', '8d': '1277339307375464499', '8h': '1277339330247000124', '8s': '1277339355916140625',
#             '9c': '1277339388057092106', '9d': '1277339409724739788', '9h': '1277339428519542906', '9s': '1277339450321539072',
#             '10c': '1277339485419339776', '10d': '1277339513815044221', '10h': '1277339543128768522', '10s': '1277339572711456908',
#             'Jc': '1277339792606105713', 'Jd': '1277339978266837093', 'Jh': '1277340066724843561', 'Js': '1277340212183433409',
#             'Qc': '1277351069097398332', 'Qd': '1277351112181153914', 'Qh': '1277351159719264377', 'Qs': '1277351187770769408',
#             'Kc': '1277350916592373761', 'Kd': '1277350949664325753', 'Kh': '1277350973676847154', 'Ks': '1277351034452316260',
#         }
#         return emoji_ids.get(card, '0')

#     def current_player_hand(self):
#         return self.player1_hand if self.current_player == self.player1 else self.player2_hand

#     async def handle_action(self, interaction: Interaction, action: str):
#         if interaction.user != self.current_player:
#             await interaction.response.send_message("It's not your turn!", ephemeral=True)
#             return

#         if action == "split":
#             await self.handle_split(interaction)
#             return

#         current_hand = self.current_player_hand()
#         current_value = self.calculate_hand_value(current_hand)

#         if action == "hit":
#             if not self.deck or len(self.deck) < 1:
#                 self.replenish_deck()
#             if not self.deck or len(self.deck) < 1:
#                 await interaction.response.send_message("The deck is out of cards, please wait or restart the game.", ephemeral=True)
#                 return

#             current_hand.append(self.deck.pop())
#             current_value = self.calculate_hand_value(current_hand)
#             if current_value >= 21:
#                 await self.end_game(interaction)
#                 return
#         elif action == "stand":
#             if self.current_player == self.player1:
#                 self.player1_stood = True
#             else:
#                 self.player2_stood = True

#         if current_value == 21 or self.check_game_over():
#             await self.end_game(interaction)
#             return

#         self.switch_player()
#         self.update_split_button()
#         embed = self.create_game_embed()
#         await interaction.response.edit_message(embed=embed, view=self)

#     async def handle_split(self, interaction: Interaction):
#         if len(self.current_player_hand()) != 2:
#             await interaction.response.send_message("You can only split with exactly two cards of the same value!", ephemeral=True)
#             return

#         hand = self.current_player_hand()
#         if hand[0][:-1] != hand[1][:-1]:
#             await interaction.response.send_message("You can only split cards of the same value!", ephemeral=True)
#             return

#         if len(self.deck) < 2:
#             self.replenish_deck()

#         split_card = hand.pop()
#         new_card1 = self.deck.pop()
#         new_card2 = self.deck.pop()

#         if self.current_player == self.player1:
#             self.player1_hand.append(new_card1)
#             self.player1_split_hand = [split_card, new_card2]
#             self.current_split_hand = self.player1_split_hand
#         else:
#             self.player2_hand.append(new_card1)
#             self.player2_split_hand = [split_card, new_card2]
#             self.current_split_hand = self.player2_split_hand

#         self.update_split_button()
#         embed = self.create_game_embed()
#         await interaction.response.edit_message(embed=embed, view=self)

#     def switch_player(self):
#         if self.current_player == self.player1:
#             self.current_player = self.player2 if not self.player2_stood else self.player1
#         else:
#             self.current_player = self.player1 if not self.player1_stood else self.player2

#     def check_game_over(self):
#         p1_value = self.calculate_hand_value(self.player1_hand)
#         p2_value = self.calculate_hand_value(self.player2_hand)
#         p1_split_value = self.calculate_hand_value(self.player1_split_hand) if self.player1_split_hand else 0
#         p2_split_value = self.calculate_hand_value(self.player2_split_hand) if self.player2_split_hand else 0
        
#         return (max(p1_value, p1_split_value) >= 21 or max(p2_value, p2_split_value) >= 21 or 
#                 (len(self.player1_hand) >= 5 and len(self.player2_hand) >= 5) or
#                 (self.player1_stood and self.player2_stood) or
#                 (self.player1_stood and max(p2_value, p2_split_value) == 21) or
#                 (self.player2_stood and max(p1_value, p1_split_value) == 21))

#     async def end_game(self, interaction: Interaction):
#         p1_value = max(self.calculate_hand_value(self.player1_hand), 
#                        self.calculate_hand_value(self.player1_split_hand) if self.player1_split_hand else 0)
#         p2_value = max(self.calculate_hand_value(self.player2_hand), 
#                        self.calculate_hand_value(self.player2_split_hand) if self.player2_split_hand else 0)

#         if p1_value == 21 and not self.player1_stood:
#             result = f"{self.player1.name} wins with Blackjack!"
#         elif p2_value == 21 and not self.player2_stood:
#             result = f"{self.player2.name} wins with Blackjack!"
#         elif p1_value > 21 and p2_value > 21:
#             result = "It's a tie! Both players busted."
#         elif p1_value > 21:
#             result = f"{self.player2.mention} wins! {self.player1.mention} busted."
#         elif p2_value > 21:
#             result = f"{self.player1.mention} wins! {self.player2.mention} busted."
#         elif p1_value > p2_value:
#             result = f"{self.player1.mention} wins with a score of {p1_value}!"
#         elif p2_value > p1_value:
#             result = f"{self.player2.mention} wins with a score of {p2_value}!"
#         else:
#             result = "It's a tie!"

#         embed = self.create_game_embed()
#         embed.add_field(name="Game Over", value=result, inline=False)

#         for child in self.children:
#             child.disabled = True

#         await interaction.response.edit_message(embed=embed, view=self)

class TicTacToeButton(Button):
    def __init__(self, game_id, x, y):
        super().__init__(style=ButtonStyle.secondary, label="\u200b", row=x, custom_id=f"tictactoe_{game_id}_{x}_{y}")
        self.game_id = game_id
        self.x = x
        self.y = y

    async def callback(self, interaction: Interaction):
        view: TicTacToeView = self.view
        if self.game_id != view.game_id:
            await interaction.response.send_message("This game is no longer active.", ephemeral=True)
            return
        
        state = view.board[self.x][self.y]

        if state in (view.X, view.O):
            await interaction.response.send_message("This tile is already claimed.", ephemeral=True)
            return

        if interaction.user.id != view.player1.id and interaction.user.id != view.player2.id:
            await interaction.response.send_message("You aren't participating in this game.", ephemeral=True)
            return

        if interaction.user.id != view.current_turn:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        if interaction.user.id == view.player1.id:
            self.style = ButtonStyle.danger
            self.label = "X"
            view.board[self.x][self.y] = view.X
            view.current_turn = view.player2.id
        else:
            self.style = ButtonStyle.success
            self.label = "O"
            view.board[self.x][self.y] = view.O
            view.current_turn = view.player1.id

        winner = view.check_winner()
        if winner:
            for child in view.children:
                child.disabled = True

            if winner == view.X:
                content = f"**{view.player1.display_name}** vs **{view.player2.display_name}**\n\n🏅 {view.player1.mention} won!"
            elif winner == view.O:
                content = f"**{view.player1.display_name}** vs **{view.player2.display_name}**\n\n🏅 {view.player2.mention} won!"
            else:
                content = f"**{view.player1.display_name}** vs **{view.player2.display_name}**\n\n🔎 Nobody won! It's a tie."

            await interaction.response.edit_message(content=content, view=view)
        else:
            turn_mention = view.player1.mention if view.current_turn == view.player1.id else view.player2.mention
            symbol = "⭕" if view.current_turn == view.player1.id else "❌"
            content = f"**{view.player1.display_name}** vs **{view.player2.display_name}**\n\n{symbol} {turn_mention}, your turn."
            await interaction.response.edit_message(content=content, view=view)

class TicTacToeView(View):
    X = -1
    O = 1
    Tie = 2

    def __init__(self, player1: discord.Member, player2: discord.Member, game_id: str, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.board = [[0] * 3 for _ in range(3)]
        self.current_turn = player1.id
        self.player1 = player1
        self.player2 = player2
        self.interaction = interaction

        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(game_id, x, y))

    def check_winner(self):
        for row in self.board:
            if abs(sum(row)) == 3:
                return self.X if row[0] == self.X else self.O

        for col in range(3):
            col_sum = self.board[0][col] + self.board[1][col] + self.board[2][col]
            if abs(col_sum) == 3:
                return self.X if self.board[0][col] == self.X else self.O

        diag1 = [self.board[0][0], self.board[1][1], self.board[2][2]]
        diag2 = [self.board[0][2], self.board[1][1], self.board[2][0]]
        if abs(sum(diag1)) == 3:
            return self.X if diag1[0] == self.X else self.O
        if abs(sum(diag2)) == 3:
            return self.X if diag2[0] == self.X else self.O

        if all(cell != 0 for row in self.board for cell in row):
            return self.Tie

        return None

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        try:
            await self.interaction.response.defer()
            await self.interaction.response.edit_message(content=f"**{self.player1.display_name}** vs **{self.player2.display_name}**\n\n⏰ The game has timed out!", view=self)
        except discord.NotFound:
            pass

class TTTAcceptButton(Button):
    def __init__(self, author: discord.Member, interaction: discord.Interaction):
        super().__init__(style=ButtonStyle.green, emoji="<:check:1344689360527949834>", custom_id=f"accept_tictactoe_{author.id}")
        self.author = author
        self.interaction = interaction

    async def callback(self, interaction: Interaction):
        try:
            if interaction.user.id == self.author.id:
                await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
                return

            game_id = str(secrets.token_hex(8))
            view = TicTacToeView(self.author, interaction.user, game_id, interaction)
            content = f"**{self.author.display_name}** vs **{interaction.user.display_name}**\n\n⭕ {self.author.mention}, your turn."
            await interaction.response.edit_message(content=content, view=view)
        except Exception as e:
            await error_handler(interaction, e)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        try:
            await self.interaction.response.defer()
            await self.interaction.response.edit_message(content="The game invitation has expired. Start a new game to play again!", view=self)
        except discord.NotFound:
            pass

class SnakeButton(Button):
    def __init__(self, label, custom_id):
        super().__init__(style=ButtonStyle.primary, label=label, custom_id=custom_id)

    async def callback(self, interaction: Interaction):
        await Games.update_snake_game(interaction, self.custom_id)

class Games(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.snake_game_sessions = {}
        self.players = []
        #self.word_list = self.load_word_list()
        #self.used_words = set()
        #self.word_dict = {}
        #self.preprocess_word_list()
        self.game_running = False

    games = app_commands.Group(
        name="games", 
        description="Minigame related commands",
        allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True, private_channel=True),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True)
    )

    @games.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def tictactoe(self, interaction: Interaction):
        "Play TicTacToe with a friend."
        button = TTTAcceptButton(interaction.user, interaction)
        view = View()
        view.add_item(button)
        await interaction.response.send_message(f"Click the button to play Tic-Tac-Toe with {interaction.user.mention}", view=view)

    @games.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=False, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def rps(self, interaction: discord.Interaction):
        "Play Rock-Paper-Scissors with a friend."
        class RPSAcceptButton(discord.ui.Button):
            def __init__(self, author: discord.Member, interaction: discord.Interaction):
                super().__init__(style=discord.ButtonStyle.green, emoji="<:check:1344689360527949834>", custom_id=f"accept_rps_{author.id}")
                self.author = author
                self.interaction = interaction

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id == self.author.id:
                    await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
                    return

                embed = discord.Embed(title="Any of you can go first", description="-# Click a button to make your move")
                view = RPSGameView(self.author, interaction.user, interaction)
                content = f"{self.author.mention} {interaction.user.mention}"
                await interaction.response.edit_message(content=content, embed=embed, view=view)

            async def on_timeout(self):
                for child in self.view.children:
                    child.disabled = True
                try:
                    await self.interaction.edit_original_response(content="The game invitation has expired. Start a new game to play again!", view=self.view)
                except discord.NotFound:
                    pass

        class RPSGameView(discord.ui.View):
            def __init__(self, player1: discord.Member, player2: discord.Member, interaction: discord.Interaction):
                super().__init__(timeout=240)
                self.player1 = player1
                self.player2 = player2
                self.player1_choice = None
                self.player2_choice = None
                self.interaction = interaction
                self.add_item(RPSButton("<a:rock:1361492026901925988>", "rock", player1, player2))
                self.add_item(RPSButton("<a:paper:1361492022820733122>", "paper", player1, player2))
                self.add_item(RPSButton("<a:scissors:1361492016894316802>", "scissors", player1, player2))

            async def check_winner(self):
                if self.player1_choice and self.player2_choice:
                    winner = None
                    if self.player1_choice == self.player2_choice:
                        winner = "tie"
                    elif (self.player1_choice == "rock" and self.player2_choice == "scissors") or \
                        (self.player1_choice == "paper" and self.player2_choice == "rock") or \
                        (self.player1_choice == "scissors" and self.player2_choice == "paper"):
                        winner = self.player1
                    else:
                        winner = self.player2

                    for child in self.children:
                        child.disabled = True

                    emoji1 = f"<a:{self.player1_choice}:1361492026901925988>" if self.player1_choice == "rock" else f"<a:{self.player1_choice}:1361492022820733122>" if self.player1_choice == "paper" else f"<a:{self.player1_choice}:1361492016894316802>"
                    emoji2 = f"<a:{self.player2_choice}:1361492026901925988>" if self.player2_choice == "rock" else f"<a:{self.player2_choice}:1361492022820733122>" if self.player2_choice == "paper" else f"<a:{self.player2_choice}:1361492016894316802>"

                    if winner == "tie":
                        result = f"**It's a tie!**\n\n-# {self.player1.display_name} chose {emoji1} & {self.player2.display_name} chose {emoji2}"
                    else:
                        winning_emoji = emoji1 if winner == self.player1 else emoji2
                        result = f"**{winner.display_name} won with {winning_emoji}**\n\n-# {self.player1.display_name} chose {emoji1} & {self.player2.display_name} chose {emoji2}"

                    embed = discord.Embed(description=result)
                    try:
                        await self.interaction.edit_original_response(content=None, embed=embed, view=self)
                    except discord.NotFound:
                        pass
                    self.stop()

            async def on_timeout(self):
                for child in self.children:
                    child.disabled = True
                embed = discord.Embed(description="Game timed out, feel free to start another.")
                try:
                    await self.interaction.edit_original_response(embed=embed, view=self)
                except discord.NotFound:
                    pass

        class RPSButton(discord.ui.Button):
            def __init__(self, emoji: str, choice: str, player1: discord.Member, player2: discord.Member):
                super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji)
                self.choice = choice
                self.player1 = player1
                self.player2 = player2

            async def callback(self, interaction: discord.Interaction):
                view: RPSGameView = self.view
                
                await interaction.response.defer()

                if interaction.user.id not in (view.player1.id, view.player2.id):
                    await interaction.followup.send("You're not part of this game!", ephemeral=True)
                    return
                
                if interaction.user.id == view.player1.id:
                    if view.player1_choice is not None:
                        await interaction.followup.send("You've already made your choice!", ephemeral=True)
                        return
                    view.player1_choice = self.choice
                else:
                    if view.player2_choice is not None:
                        await interaction.followup.send("You've already made your choice!", ephemeral=True)
                        return
                    view.player2_choice = self.choice

                if view.player1_choice and not view.player2_choice:
                    content = f"{view.player2.mention}"
                    embed = discord.Embed(description=f"{view.player1.display_name} locked their choice\n{view.player2.display_name} is choosing...")
                    await view.interaction.edit_original_response(content=content, embed=embed)
                elif view.player2_choice and not view.player1_choice:
                    content = f"{view.player1.mention}"
                    embed = discord.Embed(description=f"{view.player2.display_name} locked their choice\n{view.player1.display_name} is choosing...")
                    await view.interaction.edit_original_response(content=content, embed=embed)
                else:
                    await view.check_winner()

        button = RPSAcceptButton(interaction.user, interaction)
        view = discord.ui.View()
        view.add_item(button)
        await interaction.response.send_message(f"Click the button to play Rock-Paper-Scissors with {interaction.user.mention}", view=view)

    @games.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def snake(self, interaction: Interaction):
        "Play Snake game."
        game_id = str(interaction.user.id)
        self.snake_game_sessions[game_id] = {
            "snake": [{"x": 3, "y": 3}],
            "food": {"x": 4, "y": 4},
            "grid_size": 7,
            "direction": "none",
            "game_over": False,
            "score": 0,
            #"allow_others": allow_others,
            "author": interaction.user.id
        }

        content = (
            "-# **Control the snake using the buttons.**"
            #"-# **Control the snake using the buttons.**\n"
            #f"-# Allow others: {'true' if allow_others else 'false'}"
        )

        await interaction.response.send_message(
            content=content,
            embed=self.render_snake_game(game_id),
            view=self.get_snake_action_view()
        )
        
    @games.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def typeracer(self, interaction: Interaction):
        "Play TypeRacer."
        embed = await cembed(
            interaction,
            title="🏁 Type Racer! 🏁",
            description="Click the button below to start the type race!\n"
                        "`💡` **Tip:** Use TAB + Enter to navigate quickly!"
        )
        view = TypeRacerView(initiating_user=interaction.user)
        await interaction.response.send_message(embed=embed, view=view)

    @staticmethod
    async def update_snake_game(interaction: Interaction, direction: str):
        self = interaction.client.get_cog('Games')
        user_id = str(interaction.user.id)
        if user_id not in self.snake_game_sessions:
            await interaction.response.send_message("No snake game found for you.", ephemeral=True)
            return

        game_state = self.snake_game_sessions[user_id]
        #if not game_state["allow_others"] and interaction.user.id != game_state["author"]:
        if interaction.user.id != game_state["author"]:
            await interaction.response.send_message("You cannot interact with someone else's command.", ephemeral=True)
            return

        if game_state["game_over"]:
            await interaction.response.send_message("The game is over.", ephemeral=True)
            return

        head = game_state["snake"][0]
        new_head = {"x": head["x"], "y": head["y"]}

        if direction == "up":
            new_head["y"] -= 1
        elif direction == "down":
            new_head["y"] += 1
        elif direction == "left":
            new_head["x"] -= 1
        elif direction == "right":
            new_head["x"] += 1

        if (new_head["x"] < 0 or new_head["x"] >= game_state["grid_size"] or
            new_head["y"] < 0 or new_head["y"] >= game_state["grid_size"] or
            any(part["x"] == new_head["x"] and part["y"] == new_head["y"] for part in game_state["snake"])):
            game_state["game_over"] = True
            await interaction.response.edit_message(content=":x: Game Over! :x:", view=None)
            return

        if new_head["x"] == game_state["food"]["x"] and new_head["y"] == game_state["food"]["y"]:
            game_state["snake"].insert(0, new_head)
            game_state["score"] += 1
            self.place_snake_food(game_state)
        else:
            game_state["snake"].insert(0, new_head)
            game_state["snake"].pop()

        await interaction.response.edit_message(embed=self.render_snake_game(user_id), view=self.get_snake_action_view())

    def get_snake_action_view(self):
        view = View()
        view.add_item(SnakeButton("⬆️", "up"))
        view.add_item(SnakeButton("⬅️", "left"))
        view.add_item(SnakeButton("⬇️", "down"))
        view.add_item(SnakeButton("➡️", "right"))
        return view

    def render_snake_game(self, game_id):
        game_state = self.snake_game_sessions[game_id]
        grid_size = game_state["grid_size"]
        grid = [["⬛" for _ in range(grid_size)] for _ in range(grid_size)]

        if game_state["snake"]:
            head = game_state["snake"][0]
            grid[head["y"]][head["x"]] = "🟣" 
            
            for part in game_state["snake"][1:]:
                grid[part["y"]][part["x"]] = "🟨"

        food = game_state["food"]
        grid[food["y"]][food["x"]] = "🍎"

        grid_str = "\n".join("".join(row) for row in grid)

        embed = discord.Embed(title="Snake Game", description=grid_str, color=0x000000)
        embed.add_field(name="Score", value=str(game_state["score"]))
        return embed

    def place_snake_food(self, game_state):
        empty_spaces = [{"x": x, "y": y} for y in range(game_state["grid_size"]) for x in range(game_state["grid_size"]) if not any(part["x"] == x and part["y"] == y for part in game_state["snake"])]
        game_state["food"] = random.choice(empty_spaces)

    @games.command()
    @app_commands.allowed_installs(guilds=False, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def blackjack(self, interaction: discord.Interaction):
        "Play Blackjack with a friend."
        cards = {
            'Ac': '1277339621931614431', 'Ad': '1277339638633074829', 'Ah': '1277339670115778613', 'As': '1277339705591201834',
            '2c': '1277336190890279005', '2d': '1277336210049863762', '2h': '1277336231994327050', '2s': '1277336263481102436',
            '3c': '1277336370641113148', '3d': '1277336428807717017', '3h': '1277336449221398528', '3s': '1277336467919863828',
            '4c': '1277336519488700436', '4d': '1277336538308546560', '4h': '1277336555119444020', '4s': '1277336572005580900',
            '5c': '1277336588891721768', '5d': '1277336615597113384', '5h': '1277336674426294283', '5s': '1277336729522667531',
            '6c': '1277336776993935464', '6d': '1277336840487174258', '6h': '1277336896527274007', '6s': '1277337048034054305',
            '7c': '1277337074713755678', '7d': '1277337109761626246', '7h': '1277337138375036979', '7s': '1277339225620086987',
            '8c': '1277339252891451462', '8d': '1277339307375464499', '8h': '1277339330247000124', '8s': '1277339355916140625',
            '9c': '1277339388057092106', '9d': '1277339409724739788', '9h': '1277339428519542906', '9s': '1277339450321539072',
            '10c': '1277339485419339776', '10d': '1277339513815044221', '10h': '1277339543128768522', '10s': '1277339572711456908',
            'Jc': '1277339792606105713', 'Jd': '1277339978266837093', 'Jh': '1277340066724843561', 'Js': '1277340212183433409',
            'Qc': '1277351069097398332', 'Qd': '1277351112181153914', 'Qh': '1277351159719264377', 'Qs': '1277351187770769408',
            'Kc': '1277350916592373761', 'Kd': '1277350949664325753', 'Kh': '1277350973676847154', 'Ks': '1277351034452316260',
        }

        def calculate_hand_value(hand):
            value = 0
            aces = 0
            for card in hand:
                if card[0] in ['J', 'Q', 'K']:
                    value += 10
                elif card[0] == 'A':
                    value += 11
                    aces += 1
                else:
                    value += int(card[0])
            while value > 21 and aces:
                value -= 10
                aces -= 1
            return value

        class BlackjackButton(Button):
            def __init__(self, author: discord.Member):
                super().__init__(style=discord.ButtonStyle.green, emoji="<:check:1344689360527949834>", custom_id=f"accept_blackjack_{author.id}")
                self.author = author

            async def callback(self, interaction: discord.Interaction):
                if interaction.user.id == self.author.id:
                    await interaction.response.send_message("You cannot play against yourself!", ephemeral=True)
                    return

                deck = list(cards.keys())
                random.shuffle(deck)

                player1_hand = [deck.pop(), deck.pop()]
                player2_hand = [deck.pop(), deck.pop()]

                embed = await cembed(interaction, description=f"### __{self.author.mention}'s turn__\n**{self.author.display_name}'s hand ({calculate_hand_value(player1_hand)})**\n### {' '.join([f'<:{card}:{cards[card]}>' for card in player1_hand])}\n**{interaction.user.display_name}'s hand ({calculate_hand_value(player2_hand)})**\n### {' '.join([f'<:{card}:{cards[card]}>' for card in player2_hand])}")
                embed.set_author(name=f"{self.author.name} vs {interaction.user.name}")
                embed.set_thumbnail(url=self.author.display_avatar.url)
                embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png")

                view = BlackjackView(interaction, self.author, interaction.user, deck, player1_hand, player2_hand, cards)
                await interaction.response.edit_message(content=None, embed=embed, view=view)

        class BlackjackView(View):
            def __init__(self, interaction, player1: discord.Member, player2: discord.Member, deck: list, player1_hand: list, player2_hand: list, cards: dict):
                super().__init__(timeout=240)
                self.interaction = interaction
                self.player1 = player1
                self.player2 = player2
                self.deck = deck
                self.player1_hand = player1_hand
                self.player2_hand = player2_hand
                self.cards = cards
                self.current_turn = player1
                self.game_finished = False
                self.double_down_disabled = True
                self.update_buttons()

            def update_buttons(self):
                for item in self.children:
                    if item.label == "Double Down":
                        item.disabled = self.double_down_disabled
                        item.style = discord.ButtonStyle.gray if self.double_down_disabled else discord.ButtonStyle.secondary

            async def update_embed(self):
                description = f"### __{self.current_turn.mention}'s turn__\n**{self.player1.display_name}'s hand ({calculate_hand_value(self.player1_hand)})**\n### {' '.join([f'<:{card}:{self.cards[card]}>' for card in self.player1_hand])}\n**{self.player2.display_name}'s hand ({calculate_hand_value(self.player2_hand)})**\n### {' '.join([f'<:{card}:{self.cards[card]}>' for card in self.player2_hand])}"
                embed = await cembed(self.interaction, description=description)
                embed.set_author(name=f"{self.player1.name} vs {self.player2.name}")
                embed.set_thumbnail(url=self.current_turn.display_avatar.url)
                embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png")

                return embed

            async def check_for_21(self):
                player1_value = calculate_hand_value(self.player1_hand)
                player2_value = calculate_hand_value(self.player2_hand)

                if player1_value == 21:
                    await self.end_game(None, "21")
                elif player2_value == 21:
                    await self.end_game(None, "21")

            @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
            async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.current_turn.id:
                    await interaction.response.send_message("It's not your turn!", ephemeral=True)
                    return

                if self.current_turn == self.player1:
                    self.player1_hand.append(self.deck.pop())
                    if calculate_hand_value(self.player1_hand) > 21:
                        await self.end_game(interaction, "bust")
                        return
                else:
                    self.player2_hand.append(self.deck.pop())
                    if calculate_hand_value(self.player2_hand) > 21:
                        await self.end_game(interaction, "bust")
                        return

                self.double_down_disabled = True
                self.update_buttons()
                await self.check_for_21()
                self.current_turn = self.player2 if self.current_turn == self.player1 else self.player1
                embed = await self.update_embed()
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="Stand", style=discord.ButtonStyle.green)
            async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.current_turn.id:
                    await interaction.response.send_message("It's not your turn!", ephemeral=True)
                    return

                if self.current_turn == self.player1:
                    self.current_turn = self.player2
                    embed = await self.update_embed()
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await self.end_game(interaction, "stand")

            @discord.ui.button(label="Double Down", style=discord.ButtonStyle.gray, disabled=True)
            async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id != self.current_turn.id:
                    await interaction.response.send_message("It's not your turn!", ephemeral=True)
                    return

                if self.current_turn == self.player1:
                    self.player1_hand.append(self.deck.pop())
                    if calculate_hand_value(self.player1_hand) > 21:
                        await self.end_game(interaction, "bust")
                        return
                else:
                    self.player2_hand.append(self.deck.pop())
                    if calculate_hand_value(self.player2_hand) > 21:
                        await self.end_game(interaction, "bust")
                        return

                self.double_down_disabled = True
                self.update_buttons()
                await self.end_game(interaction, "double_down")

            async def end_game(self, interaction: discord.Interaction, reason: str):
                player1_value = calculate_hand_value(self.player1_hand)
                player2_value = calculate_hand_value(self.player2_hand)

                if reason == "bust":
                    if player1_value > 21:
                        result = f"{self.player1.mention} busts! {self.player2.mention} wins!"
                    else:
                        result = f"{self.player2.mention} busts! {self.player1.mention} wins!"
                elif reason == "21":
                    if player1_value == 21:
                        result = f"{self.player1.mention} wins with 21!"
                    elif player2_value == 21:
                        result = f"{self.player2.mention} wins with 21!"
                elif reason == "double_down":
                    if player1_value > player2_value:
                        result = f"{self.player1.mention} wins with {player1_value}!"
                    elif player2_value > player1_value:
                        result = f"{self.player2.mention} wins with {player2_value}!"
                    else:
                        result = "It's a tie!"
                else:
                    if player1_value > player2_value:
                        result = f"{self.player1.mention} wins with {player1_value}!"
                    elif player2_value > player1_value:
                        result = f"{self.player2.mention} wins with {player2_value}!"
                    else:
                        result = "It's a tie!"

                embed = discord.Embed(
                    title="Game Over!",
                    description=f"{result}\n\n**{self.player1.display_name}'s hand ({player1_value})**\n### {' '.join([f'<:{card}:{self.cards[card]}>' for card in self.player1_hand])}\n\n**{self.player2.display_name}'s hand ({player2_value})**\n### {' '.join([f'<:{card}:{self.cards[card]}>' for card in self.player2_hand])}",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url="https://git.cursi.ng/heist.png")
                embed.set_footer(text=f"{footer}", icon_url="https://git.cursi.ng/heist.png")
                self.disable_all_items()
                if interaction:
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    await interaction.response.edit_original_response(embed=embed, view=self)

            def disable_all_items(self):
                for item in self.children:
                    item.disabled = True

        view = View()
        view.add_item(BlackjackButton(interaction.user))
        await interaction.response.send_message(f"Click the button to play Blackjack with {interaction.user.mention}", view=view)

    # def load_word_list(self):
    #     with open('/heist/wordlist.txt', 'r') as file:
    #         return [word.strip().lower() for word in file.readlines()]

    # def preprocess_word_list(self):
    #     for word in self.word_list:
    #         if len(word) >= 3:
    #             prefix = word[:3]
    #             if prefix not in self.word_dict:
    #                 self.word_dict[prefix] = set()
    #             self.word_dict[prefix].add(word)

    # def is_valid_word(self, word):
    #     word = word.lower()
    #     return self.current_letters in word and word in self.word_dict.get(self.current_letters, set()) and word not in self.used_words

    # def get_random_letters(self):
    #     while True:
    #         word = random.choice(self.word_list)
    #         if len(word) >= 3:
    #             return word[:3]

    # @commands.command(name="blacktea", aliases=["bt"])
    # @commands.check(permissions.is_blacklisted)
    # @permissions.bot_requires(embed_links=True, add_reactions=True)
    # async def blacktea(self, ctx, *args):
    #     channel_id = str(ctx.channel.id)

    #     if args and args[0] == "end":
    #         if not ctx.channel.permissions_for(ctx.author).manage_messages:
    #             embed = discord.Embed(
    #                 description=f"<:warning:1301737302317596672> {ctx.author.mention}: You are missing the `manage_messages` permissions.",
    #                 color=0xf9a719
    #             )
    #             await ctx.send(embed=embed)
    #             return

    #         if redis_client.exists(channel_id):
    #             self.game_running = False
    #             initial_message_id = redis_client.get(f"{channel_id}_initial_message_id")
    #             if initial_message_id:
    #                 try:
    #                     initial_message = await ctx.channel.fetch_message(int(initial_message_id))
    #                     await initial_message.delete()
    #                 except discord.NotFound:
    #                     pass

    #             redis_client.delete(channel_id)
    #             redis_client.delete(f"{channel_id}_initial_message_id")
    #             embed = discord.Embed(
    #                 description=f"<a:vericheckg:1301736918794371094> {ctx.author.mention} has ended the ongoing BlackTea game.",
    #                 color=discord.Color.red()
    #             )
    #             await ctx.send(embed=embed)
    #             return
    #         else:
    #             embed = discord.Embed(
    #                 description=f"<:warning:1301737302317596672> {ctx.author.mention}: No ongoing game in this channel.",
    #                 color=0xf9a719
    #             )
    #             await ctx.send(embed=embed)
    #             return

    #     if redis_client.exists(channel_id):
    #         try:
    #             initial_message_id = redis_client.get(f"{channel_id}_initial_message_id")
    #             if initial_message_id:
    #                 initial_message = await ctx.channel.fetch_message(int(initial_message_id))
    #                 if initial_message:
    #                     embed = discord.Embed(
    #                         description=f"<:warning:1301737302317596672> {ctx.author.mention}: There is an ongoing BlackTea game in this channel, use `blacktea end` to stop it.",
    #                         color=0xf9a719
    #                     )
    #                     await ctx.send(embed=embed)
    #                     return
    #         except discord.NotFound:
    #             redis_client.delete(channel_id)
    #             redis_client.delete(f"{channel_id}_initial_message_id")

    #     redis_client.set(channel_id, "waiting")
    #     self.word_list = self.load_word_list()
    #     self.used_words.clear()
    #     players = []
    #     current_player_index = 0
    #     lives = {}
    #     end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=30)

    #     embed = discord.Embed(
    #         description=(
    #             "<a:loading:1269644867047260283> Waiting for **players**, react with "
    #             "<:vericheck:1301647869505179678> to join. The game will begin **{}**.\n\n"
    #             "**`GOAL`**: You have 10 seconds to say a word containing the provided set of **3** letters. "
    #             "Failing to respond within 10 seconds results in losing a life. Each player starts with **2** lives.\n\n"
    #             "**`NOTES`**: A word can only be used once through the course of the entire game."
    #         ).format(discord.utils.format_dt(end_time, style='R')),
    #         color=0x428565
    #     )
    #     embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
    #     embed.set_thumbnail(url="https://git.cursi.ng/matcha.png")
    #     message = await ctx.send(embed=embed)
    #     await message.add_reaction("<:vericheck:1301647869505179678>")

    #     redis_client.set(f"{channel_id}_initial_message_id", message.id)

    #     self.preprocess_word_list()

    #     def check(reaction, user):
    #         return user != self.client.user and str(reaction.emoji) == "<:vericheck:1301647869505179678>" and reaction.message.id == message.id

    #     try:
    #         while datetime.datetime.utcnow() < end_time:
    #             remaining_time = (end_time - datetime.datetime.utcnow()).total_seconds()
    #             reaction, user = await asyncio.wait_for(self.client.wait_for('reaction_add', check=check), timeout=remaining_time)
    #             if user not in players:
    #                 players.append(user)
    #                 lives[user.id] = 2
    #                 join_embed = discord.Embed(
    #                     description=f"{user.mention} joined the game.",
    #                     color=0x428565
    #                 )
    #                 await message.channel.send(embed=join_embed)

    #     except asyncio.TimeoutError:
    #         if len(players) < 2:
    #             await message.delete()
    #             embed = discord.Embed(
    #                 description="<:warning:1301737302317596672> Not enough players joined the game. It has been canceled.",
    #                 color=0xf9a719
    #             )
    #             await ctx.send(embed=embed)
    #             redis_client.delete(channel_id)
    #             redis_client.delete(f"{channel_id}_initial_message_id")
    #             return

    #     redis_client.set(channel_id, "active")
    #     self.current_letters = self.get_random_letters()
    #     self.game_running = True

    #     try:
    #         await message.channel.fetch_message(message.id)
    #     except discord.NotFound:
    #         redis_client.delete(channel_id)
    #         redis_client.delete(f"{channel_id}_initial_message_id")
    #         self.game_running = False
    #         return

    #     await self.start_game(ctx, channel_id, players, current_player_index, lives)

    # async def start_game(self, ctx, channel_id, players, current_player_index, lives):
    #     while len(players) > 1 and self.game_running:
    #         self.current_letters = self.get_random_letters()
    #         current_player = players[current_player_index]

    #         embed = discord.Embed(
    #             description=f"🍵 Type a **word** that contains the letters: **{self.current_letters}**.",
    #             color=discord.Color.green()
    #         )
    #         await ctx.send(current_player.mention, embed=embed)

    #         try:
    #             def check(m):
    #                 return m.author == current_player and m.channel == ctx.channel and self.is_valid_word(m.content)

    #             async def countdown():
    #                 await asyncio.sleep(5)
    #                 if self.game_running:
    #                     await ctx.send(f"<:warning:1301737302317596672> {current_player.mention}: 5 seconds left..")

    #             countdown_task = asyncio.create_task(countdown())

    #             response = await self.client.wait_for('message', timeout=10.0, check=check)
    #             word = response.content.lower()
    #             self.used_words.add(word)
    #             await response.add_reaction("✅")

    #             countdown_task.cancel()

    #         except asyncio.TimeoutError:
    #             if not self.game_running:
    #                 break
    #             lives[current_player.id] -= 1
    #             if lives[current_player.id] == 0:
    #                 leave_embed = discord.Embed(
    #                     description=f"🚪 {current_player.mention} has been kicked out!",
    #                     color=discord.Color.red()
    #                 )
    #                 await ctx.send(embed=leave_embed)
    #                 players.remove(current_player)
    #             else:
    #                 crash_embed = discord.Embed(
    #                     description=f"💥 Crash out! {current_player.mention} has {lives[current_player.id]} life{'s' if lives[current_player.id] > 1 else ''} remaining!",
    #                     color=discord.Color.orange()
    #                 )
    #                 await ctx.send(embed=crash_embed)

    #         current_player_index = (current_player_index + 1) % len(players)

    #     if self.game_running:
    #         winner = players[0]
    #         win_embed = discord.Embed(
    #             description=f"🏆 {winner.mention} has won the tea! 🏆",
    #             color=discord.Color.gold()
    #         )
    #         await ctx.send(embed=win_embed)

    #     redis_client.delete(channel_id)
    #     self.game_running = False

    @games.command()
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.check(permissions.is_blacklisted)
    async def cookie(self, interaction: Interaction):
        """Click the cookie first."""
        class CookieButton(Button):
            def __init__(self):
                super().__init__(style=ButtonStyle.green, emoji="🍪", custom_id="cookie_button")

            async def callback(self, interaction: Interaction):
                view: CookieView = self.view
                if view.winner:
                    await interaction.response.send_message(f"{view.winner.mention} clicked the cookie first! 🍪", ephemeral=True)
                    return

                view.winner = interaction.user
                for child in view.children:
                    child.disabled = True

                embed = interaction.message.embeds[0]
                embed.description = f"{interaction.user.mention} clicked the cookie first! 🍪"
                await interaction.response.edit_message(embed=embed, view=view)

        class CookieView(View):
            def __init__(self, orig_interaction):
                super().__init__(timeout=10)
                self.winner = None
                self.orig_interaction = orig_interaction
                self.add_item(CookieButton())

            async def on_timeout(self):
                for child in self.children:
                    child.disabled = True

                if not self.winner:
                    try:
                        embed = await cembed(self.orig_interaction, description="No one clicked the cookie. 🍪")
                        await self.orig_interaction.edit_original_response(embed=embed, view=self)
                    except:
                        pass

        embed = await cembed(interaction, description="Click the cookie in **5**")
        await interaction.response.send_message(embed=embed)
        
        for i in range(4, 0, -1):
            await asyncio.sleep(1)
            embed = await cembed(interaction, description=f"Click the cookie in **{i}**")
            await interaction.edit_original_response(embed=embed)
        
        await asyncio.sleep(1)
        embed = await cembed(interaction, description="Click the cookie 🍪")
        view = CookieView(interaction)
        await interaction.edit_original_response(embed=embed, view=view)

async def setup(client):
    await client.add_cog(Games(client))
