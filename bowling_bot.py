"""
🎳 Bowling Strike Mini-Game Bot  (группы + 3 страйка)
======================================================
Установка:
    pip install python-telegram-bot==20.7

Запуск:
    python bowling_bot.py

Правила:
  • Бот работает ТОЛЬКО в группах, в ЛС игнорирует все сообщения
  • Нужно выбить 3 страйка подряд — тогда открывается мини-игра
  • Страйки считаются отдельно для каждого пользователя
  • Призовая цепочка: 🐻 → 🎁 → 🚀 → 💎 → 🖼
"""

import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ─── Настройки ───────────────────────────────────────────────────────────────
BOT_TOKEN      = "8987940820:AAHaOL756or8bZq3L7BuQC5y4tj5mzhG0rE"
STRIKES_NEEDED = 3       # сколько страйков нужно для запуска игры

ROWS, COLS  = 4, 5
TOTAL_CELLS = ROWS * COLS   # 20
MINES_COUNT = 11

PRIZES = ["🐻 Мишка", "🎁 Подарок", "🚀 Ракета", "💎 Алмаз", "🖼 NFT"]

HIDDEN = "🟦"
MINE   = "💣"
SAFE   = "💫"

STRIKE_VALUE = 6   # значение dice 🎳 при страйке

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── Фильтр: только группы ───────────────────────────────────────────────────
GROUP_FILTER = filters.ChatType.GROUP | filters.ChatType.SUPERGROUP


# ─── Вспомогательные функции ─────────────────────────────────────────────────

def new_game_state() -> dict:
    mines = set(random.sample(range(TOTAL_CELLS), MINES_COUNT))
    return {
        "mines":    mines,
        "revealed": set(),
        "level":    0,
        "alive":    True,
        "active":   True,
    }


def build_keyboard(state: dict) -> InlineKeyboardMarkup:
    keyboard = []
    idx = 0
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            if idx in state["revealed"]:
                label = MINE if idx in state["mines"] else SAFE
                row.append(InlineKeyboardButton(label, callback_data=f"cd_{idx}"))
            else:
                row.append(InlineKeyboardButton(HIDDEN, callback_data=f"c_{idx}"))
            idx += 1
        keyboard.append(row)

    if state["alive"] and state["active"] and state["level"] > 0:
        keyboard.append([
            InlineKeyboardButton("💰 Забрать приз и выйти", callback_data="cashout")
        ])
    return InlineKeyboardMarkup(keyboard)


def game_text(state: dict, owner_name: str = "") -> str:
    level     = state["level"]
    collected = PRIZES[:level]
    next_p    = PRIZES[level] if level < len(PRIZES) else None

    header = "╔═══════════════════╗"
    footer = "╚═══════════════════╝"

    lines = [
        f"{header}",
        f"  🎳 *БОУЛИНГ · МИНИ-ИГРА* 🎳",
        f"{footer}",
        "",
    ]
    if owner_name:
        lines.append(f"👤 Игрок: *{owner_name}*")

    lines += [
        f"💣 Мин на поле: *{MINES_COUNT}* из {TOTAL_CELLS}",
        "",
    ]

    if collected:
        lines.append("🏅 *Собрано:*")
        lines.append("  " + "  ".join(collected))
        lines.append("")

    if next_p:
        lines.append(f"🎯 *Следующий приз:* {next_p}")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━━",
        "Выбери ячейку 👇",
    ]
    return "\n".join(lines)


async def launch_minigame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = new_game_state()
    user = update.effective_user
    state["owner_id"]   = user.id
    state["owner_name"] = user.first_name
    context.user_data["game"]    = state
    context.user_data["strikes"] = 0   # сбрасываем счётчик
    kb = build_keyboard(state)
    await update.effective_message.reply_text(
        game_text(state, user.first_name), reply_markup=kb, parse_mode="Markdown"
    )


# ─── Команды (только в группах) ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Молчим в ЛС
    if update.effective_chat.type == "private":
        return
    chain = "  →  ".join(PRIZES)
    await update.message.reply_text(
        f"╔═══════════════════╗\n"
        f"  🎳 *БОУЛИНГ · БОТ* 🎳\n"
        f"╚═══════════════════╝\n"
        f"\n📋 *Как играть:*\n"
        f"  1️⃣ Отправь стикер 🎳\n"
        f"  2️⃣ Набери *{STRIKES_NEEDED} страйка*\n"
        f"  3️⃣ Открой мини-игру!\n"
        f"  4️⃣ Избегай 💣 мин\n"
        f"\n🏅 *Призовая цепочка:*\n"
        f"  {chain}\n"
        f"\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"Удачи! 🍀",
        parse_mode="Markdown"
    )


# ─── Обработчик боулинг-дайса 🎳 ─────────────────────────────────────────────

async def handle_bowling_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.dice:
        return

    # Молчим в ЛС
    if update.effective_chat.type == "private":
        return

    # Игнорируем пересланные — у них заполнен forward_date
    if msg.forward_date:
        logger.info("Ignoring forwarded dice")
        return

    value = msg.dice.value
    logger.info(f"Bowling dice value: {value} from user {update.effective_user.id}")

    if value == STRIKE_VALUE:
        strikes = context.user_data.get("strikes", 0) + 1
        context.user_data["strikes"] = strikes
        remaining = STRIKES_NEEDED - strikes

        if strikes < STRIKES_NEEDED:
            bar = "🎳" * strikes + "⬜" * remaining
            word = "страйк" if remaining == 1 else "страйка" if remaining in (2, 3, 4) else "страйков"
            await msg.reply_text(
                f"🎳 *СТРАЙК!*\n"
                f"┌─────────────────┐\n"
                f"  {bar}  {strikes}/{STRIKES_NEEDED}\n"
                f"└─────────────────┘\n"
                f"До мини-игры ещё *{remaining} {word}*!",
                parse_mode="Markdown"
            )
        else:
            await msg.reply_text(
                "🔥 *3 СТРАЙКА НАБРАНО!*\n┌─────────────────┐\n  🎳🎳🎳  НЕВЕРОЯТНО!\n└─────────────────┘\nЗапускаю мини-игру... 🎮",
                parse_mode="Markdown"
            )
            await launch_minigame(update, context)
    # Не страйк — молчим, счётчик не сбрасываем


# ─── Обработчик нажатий на поле ──────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Молчим в ЛС (на всякий случай)
    if update.effective_chat.type == "private":
        return

    state: dict = context.user_data.get("game")

    # ── Забрать приз ──────────────────────────────────────────────────────
    if query.data == "cashout":
        if not state or not state["active"]:
            await query.answer("Игра уже завершена.", show_alert=True)
            return
        if query.from_user.id != state.get("owner_id"):
            await query.answer(
                f"🚫 Это поле {state.get('owner_name', 'другого игрока')}!",
                show_alert=True
            )
            return
        state["active"] = False
        collected = PRIZES[:state["level"]]
        prizes_str = "  ".join(collected) if collected else "ничего 😢"
        text = (
            f"╔═══════════════════╗\n"
            f"  💰 *ЗАБРАЛ ПРИЗЫ!*\n"
            f"╚═══════════════════╝\n"
            f"\n🏅 Уходишь с:\n  {prizes_str}\n"
            f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"Набери 3 страйка снова 🎳"
        )
        await query.edit_message_text(text, parse_mode="Markdown")
        return

    # ── Уже открытая ячейка ───────────────────────────────────────────────
    if query.data.startswith("cd_"):
        return

    if not query.data.startswith("c_"):
        return

    if not state or not state["active"]:
        await query.answer("❌ Нет активной игры. Набери 3 страйка!", show_alert=True)
        return

    # Только владелец поля может нажимать
    if query.from_user.id != state.get("owner_id"):
        await query.answer(
            f"🚫 Это поле {state.get('owner_name', 'другого игрока')}!",
            show_alert=True
        )
        return

    cell_idx = int(query.data[2:])
    if cell_idx in state["revealed"]:
        return

    state["revealed"].add(cell_idx)

    # ── Мина ─────────────────────────────────────────────────────────────
    if cell_idx in state["mines"]:
        state["alive"] = False
        state["active"] = False
        state["revealed"].update(state["mines"])
        # Сбрасываем счётчик страйков — нужно набирать заново
        context.user_data["strikes"] = 0

        collected = PRIZES[:state["level"]]
        kb = build_keyboard(state)
        lost = ("Ничего не было собрано 😢"
                if not collected
                else "Потеряно: " + " | ".join(collected) + " 😢")
        text = (
            f"╔═══════════════════╗\n"
            f"  💣 *ВЗРЫВ! МИНА!* 💣\n"
            f"╚═══════════════════╝\n"
            f"\n{lost}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Счётчик сброшен — набери 3 страйка снова 🎳"
        )
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # ── Безопасная ячейка ─────────────────────────────────────────────────
    prize = PRIZES[state["level"]]
    state["level"] += 1

    # Все 5 призов собраны — победа
    if state["level"] >= len(PRIZES):
        state["active"] = False
        state["revealed"].update(set(range(TOTAL_CELLS)) - state["mines"])
        kb = build_keyboard(state)
        all_prizes = "  →  ".join(PRIZES)
        text = (
            f"╔═══════════════════╗\n"
            f"  👑 *МЕГА-ПОБЕДА!* 👑\n"
            f"╚═══════════════════╝\n"
            f"\nТы собрал ВСЕ призы:\n"
            f"\n  {all_prizes}\n"
            f"\n━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎳 Ты легенда боулинга! 🎳"
        )
        await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")
        return

    # Новый уровень — перетасовать мины
    state["mines"]    = set(random.sample(range(TOTAL_CELLS), MINES_COUNT))
    state["revealed"] = set()

    next_prize = PRIZES[state["level"]]
    collected_str = "  ".join(PRIZES[:state["level"]])
    text = (
        f"╔═══════════════════╗\n"
        f"  💫 *БЕЗОПАСНО!* +{prize}\n"
        f"╚═══════════════════╝\n"
        f"\n🏅 Собрано:\n  {collected_str}\n"
        f"\n🎯 Следующий: *{next_prize}*\n"
        f"\n━━━━━━━━━━━━━━━━━━━━━\n"
        f"Поле обновлено — выбирай ячейку 👇\n"
        f"_(или забери приз кнопкой ниже)_"
    )
    kb = build_keyboard(state)
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


# ─── Запуск ───────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды — только в группах
    app.add_handler(CommandHandler("start", cmd_start, filters=GROUP_FILTER))

    # Боулинг-дайс — ловим во всех чатах, проверка на группу внутри хендлера
    app.add_handler(
        MessageHandler(filters.Dice.BOWLING, handle_bowling_dice)
    )

    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Бот запущен. Работает только в группах, ждёт 3 страйка (в любое время) 🎳")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()