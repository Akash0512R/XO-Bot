import random
import asyncio
import json, os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ==============================
# GLOBAL DATA
# ==============================
games = {}
symbols = {"X": "❌", "O": "⭕", " ": "⬜"}
LEADERBOARD_FILE = "leaderboard.json"

# ==============================
# PERSISTENT LEADERBOARD
# ==============================
def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        with open(LEADERBOARD_FILE, "r") as f:
            return json.load(f)
    return {}

def save_leaderboard(data):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f, indent=4)

leaderboard = load_leaderboard()

def add_points(chat_id, player_name, points):
    chat_id = str(chat_id)
    if chat_id not in leaderboard:
        leaderboard[chat_id] = {}
    leaderboard[chat_id][player_name] = leaderboard[chat_id].get(player_name, 0) + points
    save_leaderboard(leaderboard)

def get_player_name(user):
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name.strip()

# ==============================
# GAME LOGIC
# ==============================
def create_board():
    return [[" " for _ in range(3)] for _ in range(3)]

def render_board(board):
    keyboard = []
    for i, row in enumerate(board):
        buttons = []
        for j, cell in enumerate(row):
            buttons.append(InlineKeyboardButton(symbols[cell], callback_data=f"move:{i},{j}"))
        keyboard.append(buttons)
    return InlineKeyboardMarkup(keyboard)

def check_winner(board):
    for row in board:
        if row[0] != " " and row[0] == row[1] == row[2]:
            return row[0]
    for col in range(3):
        if board[0][col] != " " and board[0][col] == board[1][col] == board[2][col]:
            return board[0][col]
    if board[0][0] != " " and board[0][0] == board[1][1] == board[2][2]:
        return board[0][0]
    if board[0][2] != " " and board[0][2] == board[1][1] == board[2][0]:
        return board[0][2]
    return None

def is_draw(board):
    return all(cell != " " for row in board for cell in row)

# ==============================
# AI
# ==============================
def ai_move(board, difficulty="hard"):
    if difficulty == "easy":
        moves = [(i,j) for i in range(3) for j in range(3) if board[i][j]==" "]
        return random.choice(moves) if moves else None
    else:
        best_score = -float("inf")
        best_move = None
        for i in range(3):
            for j in range(3):
                if board[i][j]==" ":
                    board[i][j] = "O"
                    score = minimax(board, 0, False)
                    board[i][j] = " "
                    if score > best_score:
                        best_score = score
                        best_move = (i,j)
        return best_move

def minimax(board, depth, is_max):
    winner = check_winner(board)
    if winner=="O": return 10-depth
    if winner=="X": return depth-10
    if is_draw(board): return 0

    if is_max:
        best_score = -float("inf")
        for i in range(3):
            for j in range(3):
                if board[i][j]==" ":
                    board[i][j] = "O"
                    score = minimax(board, depth+1, False)
                    board[i][j] = " "
                    best_score = max(score, best_score)
        return best_score
    else:
        best_score = float("inf")
        for i in range(3):
            for j in range(3):
                if board[i][j]==" ":
                    board[i][j] = "X"
                    score = minimax(board, depth+1, True)
                    board[i][j] = " "
                    best_score = min(score, best_score)
        return best_score

def play_again_keyboard(force=False):
    if force:
        return InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ REMATCH (No Escape)", callback_data="restart")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Play Again", callback_data="restart")]])

# ==============================
# BOT HANDLERS
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 Vs Player", callback_data="mode:player")],
        [InlineKeyboardButton("🤖 Vs AI", callback_data="mode:ai")],
    ]
    text = "🎲 *Welcome to XO Arena!*\nChoose your mode 👇"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    chat_id = str(chat.id)
    chat_title = chat.title if chat.type!="private" else get_player_name(update.message.from_user)

    if chat_id not in leaderboard or not leaderboard[chat_id]:
        await update.message.reply_text(f"📊 Leaderboard – {chat_title} is empty! Play some games first.")
        return

    sorted_scores = sorted(leaderboard[chat_id].items(), key=lambda x:x[1], reverse=True)
    msg = f"🏆 *Leaderboard – {chat_title}* 🏆\n\n"
    for rank, (player, score) in enumerate(sorted_scores, start=1):
        msg += f"{rank}. {player} – {score} points\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ==============================
# MAIN GAME HANDLER
# ==============================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data.startswith("mode:"):
        mode = query.data.split(":")[1]
        if mode=="player":
            games[chat_id] = {"board":create_board(), "turn":"X", "mode":"player", "players":{}}
            games[chat_id]["players"]["X"] = get_player_name(query.from_user)
            await query.edit_message_text(
                f"🎮 *2 Player Mode*\n\n❌ {games[chat_id]['players']['X']} is X\n⭕ Waiting for O...",
                reply_markup=render_board(games[chat_id]["board"]), parse_mode="Markdown"
            )
        else:
            keyboard = [[InlineKeyboardButton("😅 Easy AI", callback_data="ai:easy")],
                        [InlineKeyboardButton("😈 Hard AI", callback_data="ai:hard")]]
            await query.edit_message_text("🤖 Choose AI difficulty:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data.startswith("ai:"):
        difficulty = query.data.split(":")[1]
        games[chat_id] = {"board":create_board(), "turn":"X", "mode":"ai",
                          "difficulty":difficulty, "player":get_player_name(query.from_user)}
        await query.edit_message_text(
            f"🤖 *AI Mode* – Difficulty: {difficulty.capitalize()}\n\n❌ {games[chat_id]['player']} (You)\n⭕ AI Villain",
            reply_markup=render_board(games[chat_id]["board"]), parse_mode="Markdown"
        )
    elif query.data.startswith("move:"):
        await handle_move(query, chat_id, query.data)
    elif query.data=="restart":
        if chat_id in games: del games[chat_id]
        await start(update, context)

async def handle_move(query, chat_id, data):
    game = games[chat_id]
    board, turn, mode = game["board"], game["turn"], game["mode"]
    i,j = map(int, data.split(":")[1].split(","))
    player_name = get_player_name(query.from_user)

    # Prevent same player as both X and O
    if mode=="player" and turn=="O":
        if "O" not in game["players"] and player_name != game["players"].get("X"):
            game["players"]["O"] = player_name
        elif player_name == game["players"].get("X"):
            await query.answer("⛔ You cannot play both X and O!", show_alert=True)
            return

    # Restrict turn
    if mode=="player":
        if turn not in game["players"] or game["players"][turn] != player_name:
            await query.answer("⛔ It's not your turn!", show_alert=True)
            return

    if board[i][j]!=" ": return
    board[i][j] = turn
    game["turn"] = "O" if turn=="X" else "X"

    # Check winner
    winner = check_winner(board)
    if winner:
        if mode=="ai":
            player = game["player"]
            if winner=="X":
                points = 50 if game["difficulty"]=="hard" else 3
                add_points(chat_id, player, points)
                await query.edit_message_text(f"🏆 *You win!* 🎉\n\n⚔️ REMATCH?", reply_markup=play_again_keyboard(force=True), parse_mode="Markdown")
            else:
                await query.edit_message_text("🏆 🤖 AI wins!\n😈 I am unbeatable.", reply_markup=play_again_keyboard(), parse_mode="Markdown")
        else:
            winner_name = game["players"].get(winner,f"Player {winner}")
            add_points(chat_id, winner_name, 3)
            await query.edit_message_text(
                f"🏆 {symbols[winner]} wins! 🎉 {winner_name}\n❌ {game['players'].get('X','?')} vs ⭕ {game['players'].get('O','?')}",
                reply_markup=play_again_keyboard(), parse_mode="Markdown")
        del games[chat_id]
        return

    # Draw
    if is_draw(board):
        if mode=="ai":
            add_points(chat_id, game["player"], 1)
        else:
            for p in game["players"].values():
                add_points(chat_id, p, 1)
        await query.edit_message_text("🤝 It's a draw!", reply_markup=play_again_keyboard(), parse_mode="Markdown")
        del games[chat_id]
        return

    # Next turn
    if mode=="player":
        x_name = game["players"].get("X","Unknown")
        o_name = game["players"].get("O","Unknown")
        await query.edit_message_text(f"🎮 *{symbols[game['turn']]}’s turn*\n❌ {x_name}\n⭕ {o_name}", reply_markup=render_board(board), parse_mode="Markdown")
    else:
        if game["turn"]=="O":
            await asyncio.sleep(1)
            move = ai_move(board, game["difficulty"])
            if move:
                board[move[0]][move[1]] = "O"
                game["turn"]="X"
            winner = check_winner(board)
            if winner:
                player = game["player"]
                if winner=="O":
                    await query.edit_message_text("🏆 🤖 AI wins!", reply_markup=play_again_keyboard(), parse_mode="Markdown")
                else:
                    points = 50 if game["difficulty"]=="hard" else 3
                    add_points(chat_id, player, points)
                    await query.edit_message_text(f"🏆 *You win!* 🎉", reply_markup=play_again_keyboard(force=True), parse_mode="Markdown")
                del games[chat_id]
                return
            elif is_draw(board):
                add_points(chat_id, game["player"], 1)
                await query.edit_message_text("🤝 It's a draw!", reply_markup=play_again_keyboard(), parse_mode="Markdown")
                del games[chat_id]
                return
        await query.edit_message_text(f"🎮 Your turn!\n❌ {game['player']} (You)\n⭕ AI Villain", reply_markup=render_board(board), parse_mode="Markdown")

# ==============================
# BOT STARTUP
# ==============================
def main():
    app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 XO Villain Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
