import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ai import get_ai_response
from catalog import FLOWERS, get_catalog_text, find_flower_key
from orders import process_order, parse_order_from_ai
from database import (
    save_message, get_orders, get_all_orders, get_stats,
    get_flower_photos, save_flower_photo, update_inventory, set_inventory,
    get_inventory_dict,
)
from config import SHOP_NAME, ADMIN_CHAT_ID, SHOP_ADDRESS, SHOP_HOURS


def _is_admin(chat_id: int) -> bool:
    return ADMIN_CHAT_ID and chat_id == ADMIN_CHAT_ID


# --- Команда /start ---

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if _is_admin(chat_id):
        welcome = (
            f"Добро пожаловать, владелец *{SHOP_NAME}*! 🌸\n\n"
            "Я ваш помощник по управлению магазином.\n\n"
            "Что я умею:\n"
            "• Отправьте фото — я сохраню его в каталог\n"
            "• Напишите «привезли 50 роз» — обновлю склад\n"
            "• Напишите «осталось 20 роз» — установлю точное количество\n"
            "• /inventory — текущие остатки\n"
            "• /stats — статистика заказов\n"
        )
        await update.message.reply_text(welcome, parse_mode="Markdown")
    else:
        welcome = (
            f"Добро пожаловать в *{SHOP_NAME}*! 🌸\n\n"
            "Я помогу выбрать цветы и оформить заказ.\n\n"
            "Команды:\n"
            "/catalog — каталог цветов\n"
            "/myorders — мои заказы\n"
        )
        keyboard = [
            [
                InlineKeyboardButton("🌹 Каталог", callback_data="cmd_catalog"),
                InlineKeyboardButton("💐 Заказать", callback_data="cmd_order"),
            ]
        ]
        await update.message.reply_text(
            welcome,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )


# --- Команда /catalog ---

async def catalog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_catalog(update.effective_chat.id, context)


async def _send_catalog(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id, get_catalog_text(), parse_mode="Markdown")

    for key, flower in FLOWERS.items():
        photos = await get_flower_photos(key, "reference")
        if photos:
            try:
                await context.bot.send_photo(
                    chat_id,
                    photo=photos[0]["file_id"],
                    caption=f"{flower['name']} — {flower['price']} {flower['unit']}",
                )
            except Exception:
                pass

    keyboard = _build_flower_buttons()
    await context.bot.send_message(
        chat_id,
        "Выберите цветы или напишите, что хотите 👇",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _build_flower_buttons() -> list[list[InlineKeyboardButton]]:
    buttons = []
    row = []
    for key, flower in FLOWERS.items():
        row.append(InlineKeyboardButton(
            f"{flower['name']} ({flower['price']} тг)",
            callback_data=f"flower_{key}",
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return buttons


# --- Команда /myorders ---

async def myorders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await _show_orders(chat_id, update.message, context)


async def _show_orders(chat_id: int, message, context: ContextTypes.DEFAULT_TYPE):
    """Показывает заказы клиента — используется и командой /myorders и текстом."""
    orders = await get_orders(chat_id)

    if not orders:
        await message.reply_text("У вас пока нет заказов 🌸")
        return

    text = "📋 Ваши заказы:\n\n"
    for i, o in enumerate(orders[:5], 1):
        status_emoji = "✅" if o["status"] == "confirmed" else "❌"
        flowers = o.get("flowers", "—")
        qty = o.get("quantity", 0)
        total = o.get("total_price", 0)
        date = o.get("pickup_date", "")
        time = o.get("pickup_time", "")
        delivery = "самовывоз" if o.get("delivery_type") == "pickup" else "доставка"
        address = o.get("delivery_address", "")

        text += f"{i}. {status_emoji} {flowers}"
        if qty:
            text += f" x {qty} шт"
        if total:
            text += f" — {total:,} тг"
        text += "\n"
        if date:
            text += f"   Дата: {date}"
            if time:
                text += f" {time}"
            text += "\n"
        text += f"   {delivery.capitalize()}"
        if address and delivery == "доставка":
            text += f": {address}"
        text += "\n\n"

    await message.reply_text(text)


# --- Команда /inventory (только админ) ---

async def inventory_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not _is_admin(chat_id):
        await update.message.reply_text("⛔ Эта команда доступна только администратору.")
        return

    inventory = await get_inventory_dict()
    if not inventory:
        await update.message.reply_text("📦 Склад пуст. Напишите мне о поступлении цветов.")
        return

    text = "📦 *Остатки на складе:*\n\n"
    for key, flower in FLOWERS.items():
        qty = inventory.get(key, 0)
        emoji = "✅" if qty > 0 else "❌"
        text += f"{emoji} {flower['name']}: {qty} шт\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# --- Админ: /orders (все заказы) ---

async def orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not _is_admin(chat_id):
        await update.message.reply_text("⛔ Эта команда доступна только администратору.")
        return

    orders = await get_all_orders(10)
    if not orders:
        await update.message.reply_text("📋 Заказов пока нет.")
        return

    text = "📋 Все заказы:\n\n"
    for i, o in enumerate(orders[:10], 1):
        status_emoji = "✅" if o["status"] == "confirmed" else "❌"
        flowers = o.get("flowers", "—")
        qty = o.get("quantity", 0)
        total = o.get("total_price", 0)
        name = o.get("customer_name", "")
        phone = o.get("customer_phone", "")
        date = o.get("pickup_date", "")

        text += f"{i}. {status_emoji} {flowers}"
        if qty:
            text += f" x {qty} шт"
        if total:
            text += f" — {total:,} тг"
        text += "\n"
        if name:
            text += f"   Клиент: {name}"
            if phone:
                text += f" ({phone})"
            text += "\n"
        if date:
            text += f"   Дата: {date}\n"
        text += "\n"

    await update.message.reply_text(text)


# --- Админ: /stats ---

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if ADMIN_CHAT_ID and chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Эта команда доступна только администратору.")
        return

    args = context.args
    period = args[0] if args else "day"
    if period not in ("day", "week", "month"):
        period = "day"

    stats = await get_stats(period)
    period_names = {"day": "сегодня", "week": "за неделю", "month": "за месяц"}

    text = f"📊 *Статистика {period_names[period]}:*\n\n"
    text += f"Всего заказов: {stats['total_orders']}\n"
    text += f"Подтверждённых: {stats['confirmed']}\n"
    text += f"Отменённых: {stats['cancelled']}\n"
    text += f"Выручка: {stats['revenue']:,} тг\n\n"

    if stats["top_flowers"]:
        text += "🌸 *Популярные цветы:*\n"
        for flower, count in stats["top_flowers"]:
            text += f"  • {flower} — {count} заказов\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# --- Админ: /admin (показать chat_id) ---

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Ваш Chat ID: `{chat_id}`\n\n"
        "Добавьте его в .env как ADMIN_CHAT_ID чтобы получать уведомления о заказах.",
        parse_mode="Markdown",
    )


# --- Обработка фото (админ загружает фото цветов) ---

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not _is_admin(chat_id):
        await update.message.reply_text("Я принимаю только текстовые сообщения 🌸")
        return

    photo = update.message.photo[-1]
    file_id = photo.file_id

    context.user_data["pending_photo"] = file_id

    keyboard = []
    row = []
    for key, flower in FLOWERS.items():
        row.append(InlineKeyboardButton(flower["name"], callback_data=f"photo_flower_{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "📷 Фото получено! Какой это цветок?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# --- Обработка документов (webp и другие изображения) ---

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    doc = update.message.document

    if not doc or not doc.mime_type:
        return

    # Принимаем изображения отправленные как документ (webp, png, jpg и т.д.)
    if not doc.mime_type.startswith("image/"):
        if _is_admin(chat_id):
            await update.message.reply_text("Отправьте фото как изображение (не файл).")
        return

    if not _is_admin(chat_id):
        await update.message.reply_text("Я принимаю только текстовые сообщения 🌸")
        return

    file_id = doc.file_id

    context.user_data["pending_photo"] = file_id

    keyboard = []
    row = []
    for key, flower in FLOWERS.items():
        row.append(InlineKeyboardButton(flower["name"], callback_data=f"photo_flower_{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        "📷 Фото получено! Какой это цветок?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# --- Inline-кнопки (callback) ---

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data

    if data == "cmd_catalog":
        await _send_catalog(chat_id, context)
        return

    if data == "cmd_order":
        keyboard = _build_flower_buttons()
        await context.bot.send_message(
            chat_id,
            "Какие цветы хотите заказать? 🌸",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # --- Админ: выбор цветка для фото ---
    if data.startswith("photo_flower_") and _is_admin(chat_id):
        flower_key = data.replace("photo_flower_", "")
        if flower_key in FLOWERS:
            context.user_data["pending_photo_flower"] = flower_key
            # Убираем кнопки выбора цветка, показываем что выбрал
            try:
                await query.edit_message_text(
                    f"📷 Цветок: *{FLOWERS[flower_key]['name']}*",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            keyboard = [
                [
                    InlineKeyboardButton("📸 Справочное фото", callback_data="photo_type_reference"),
                    InlineKeyboardButton("💐 Фото букета", callback_data="photo_type_bouquet"),
                ]
            ]
            await context.bot.send_message(
                chat_id,
                "Это справочное фото или фото готового букета?",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    # --- Админ: выбор типа фото ---
    if data.startswith("photo_type_") and _is_admin(chat_id):
        photo_type = data.replace("photo_type_", "")
        file_id = context.user_data.get("pending_photo")
        flower_key = context.user_data.get("pending_photo_flower")

        # Убираем кнопки типа фото
        try:
            type_label = "Справочное фото" if photo_type == "reference" else "Фото букета"
            await query.edit_message_text(f"Тип: {type_label}")
        except Exception:
            pass

        if file_id and flower_key:
            await save_flower_photo(flower_key, photo_type, file_id)

            if photo_type == "bouquet":
                await update_inventory(flower_key, 1)
                await context.bot.send_message(
                    chat_id,
                    f"✅ Фото букета *{FLOWERS[flower_key]['name']}* сохранено! Инвентарь +1.",
                    parse_mode="Markdown",
                )
            else:
                await context.bot.send_message(
                    chat_id,
                    f"✅ Справочное фото *{FLOWERS[flower_key]['name']}* сохранено!",
                    parse_mode="Markdown",
                )

            context.user_data.pop("pending_photo", None)
            context.user_data.pop("pending_photo_flower", None)
        return

    # Выбор цветка клиентом — запоминаем и спрашиваем количество
    if data.startswith("flower_"):
        flower_key = data.replace("flower_", "")
        if flower_key in FLOWERS:
            flower = FLOWERS[flower_key]

            # Запоминаем выбранный цветок чтобы если клиент напишет число — мы знали какой цветок
            context.user_data["selected_flower"] = flower_key

            # Отправляем reference-фото из БД
            photos = await get_flower_photos(flower_key, "reference")
            if photos:
                try:
                    await context.bot.send_photo(
                        chat_id,
                        photo=photos[0]["file_id"],
                        caption=f"{flower['name']} — {flower['price']} {flower['unit']}",
                    )
                except Exception:
                    await context.bot.send_message(
                        chat_id,
                        f"🌸 {flower['name']} — {flower['price']} {flower['unit']}",
                    )
            else:
                await context.bot.send_message(
                    chat_id,
                    f"🌸 {flower['name']} — {flower['price']} {flower['unit']}",
                )

            # Кнопки количества
            keyboard = [
                [
                    InlineKeyboardButton("1 шт", callback_data=f"qty_{flower_key}_1"),
                    InlineKeyboardButton("3 шт", callback_data=f"qty_{flower_key}_3"),
                    InlineKeyboardButton("5 шт", callback_data=f"qty_{flower_key}_5"),
                ],
                [
                    InlineKeyboardButton("7 шт", callback_data=f"qty_{flower_key}_7"),
                    InlineKeyboardButton("11 шт", callback_data=f"qty_{flower_key}_11"),
                    InlineKeyboardButton("21 шт", callback_data=f"qty_{flower_key}_21"),
                ],
            ]
            await context.bot.send_message(
                chat_id,
                "Сколько штук? (или напишите своё число)",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    # Выбор количества — убираем кнопки и передаём в AI
    if data.startswith("qty_"):
        parts = data.split("_")
        flower_key = "_".join(parts[1:-1])
        qty = parts[-1]

        # Убираем кнопки количества
        try:
            await query.edit_message_text(f"Выбрано: {qty} шт")
        except Exception:
            pass

        if flower_key in FLOWERS:
            flower_name = FLOWERS[flower_key]["name"]
            user_msg = f"Хочу {qty} шт {flower_name}"
            context.user_data.pop("selected_flower", None)
            await _process_ai_message(chat_id, user_msg, context)
        return

    # Доставка/Самовывоз
    if data == "delivery":
        try:
            await query.edit_message_text("Выбрано: 🚚 Доставка")
        except Exception:
            pass
        await _process_ai_message(chat_id, "Доставка", context)
        return
    if data == "pickup":
        try:
            await query.edit_message_text("Выбрано: 📍 Самовывоз")
        except Exception:
            pass
        await _process_ai_message(chat_id, "Самовывоз", context)
        return

    # Оплата
    if data.startswith("pay_"):
        method = data.replace("pay_", "").replace("_", " ")
        try:
            await query.edit_message_text(f"Выбрано: 💳 {method}")
        except Exception:
            pass
        await _process_ai_message(chat_id, f"Оплата: {method}", context)
        return


# --- Обработка текстовых сообщений ---

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    # «мои заказы» текстом — работает как /myorders
    if user_text.strip().lower() in ("мои заказы", "мой заказ", "заказы"):
        await _show_orders(chat_id, update.message, context)
        return

    # Если клиент выбрал цветок кнопкой и теперь пишет число — подставляем название цветка
    selected = context.user_data.get("selected_flower")
    if selected and selected in FLOWERS and user_text.strip().isdigit():
        flower_name = FLOWERS[selected]["name"]
        user_text = f"Хочу {user_text.strip()} шт {flower_name}"
        context.user_data.pop("selected_flower", None)

    await _process_ai_message(chat_id, user_text, context)


async def _process_ai_message(chat_id: int, user_text: str, context: ContextTypes.DEFAULT_TYPE):
    """Общая логика: отправить в AI, обработать ответ, отправить клиенту."""
    await save_message(chat_id, "user", user_text)

    ai_reply = await get_ai_response(chat_id, user_text)

    # Проверяем триггеры заказа
    order_data = None
    if "ЗАКАЗ_ПОДТВЕРЖДЁН" in ai_reply:
        order_data = parse_order_from_ai(ai_reply, chat_id)
    cleaned = await process_order(ai_reply, chat_id)
    if cleaned:
        print(f"[ORDER] Заказ обработан для chat_id={chat_id}, is_admin={_is_admin(chat_id)}", flush=True)
        ai_reply = cleaned
        if ADMIN_CHAT_ID and not _is_admin(chat_id):
            await _notify_admin(chat_id, order_data, context)
        else:
            print(f"[ORDER] Уведомление пропущено: ADMIN_CHAT_ID={ADMIN_CHAT_ID}, is_admin={_is_admin(chat_id)}", flush=True)

    # Проверяем триггеры инвентаря (только для админа)
    if _is_admin(chat_id):
        # ИНВЕНТАРЬ:key:+N или ИНВЕНТАРЬ:key:-N (добавить/вычесть)
        inv_delta_matches = re.findall(r"ИНВЕНТАРЬ:(\S+):([+-]\d+)", ai_reply)
        for flower_key, delta_str in inv_delta_matches:
            flower_key = flower_key.strip().lower()
            delta = int(delta_str)
            if flower_key in FLOWERS:
                await update_inventory(flower_key, delta)

        # ИНВЕНТАРЬ:key:=N (установить точное количество)
        inv_set_matches = re.findall(r"ИНВЕНТАРЬ:(\S+):=(\d+)", ai_reply)
        for flower_key, qty_str in inv_set_matches:
            flower_key = flower_key.strip().lower()
            qty = int(qty_str)
            if flower_key in FLOWERS:
                await set_inventory(flower_key, qty)

        if inv_delta_matches or inv_set_matches:
            ai_reply = re.sub(r"ИНВЕНТАРЬ:\S+:[+-=]?\d+", "", ai_reply).strip()

    # Проверяем запрос на справочное фото
    photo_match = re.findall(r"ФОТО:(\S+)", ai_reply)
    if photo_match:
        for flower_key in photo_match:
            flower_key = flower_key.strip().lower()
            if flower_key in FLOWERS:
                photos = await get_flower_photos(flower_key, "reference")
                if photos:
                    try:
                        await context.bot.send_photo(
                            chat_id,
                            photo=photos[0]["file_id"],
                            caption=f"{FLOWERS[flower_key]['name']} — {FLOWERS[flower_key]['price']} {FLOWERS[flower_key]['unit']}",
                        )
                    except Exception:
                        await context.bot.send_message(
                            chat_id,
                            f"🌸 {FLOWERS[flower_key]['name']} — к сожалению, фото пока нет.",
                        )
                else:
                    await context.bot.send_message(
                        chat_id,
                        f"🌸 {FLOWERS[flower_key]['name']} — фото пока не загружено.",
                    )
        ai_reply = re.sub(r"ФОТО:\S+", "", ai_reply).strip()

    # Проверяем запрос на фото букета
    bouquet_match = re.findall(r"БУКЕТ:(\S+)", ai_reply)
    if bouquet_match:
        for flower_key in bouquet_match:
            flower_key = flower_key.strip().lower()
            if flower_key in FLOWERS:
                photos = await get_flower_photos(flower_key, "bouquet")
                if photos:
                    try:
                        await context.bot.send_photo(
                            chat_id,
                            photo=photos[0]["file_id"],
                            caption=f"💐 Готовый букет: {FLOWERS[flower_key]['name']}",
                        )
                    except Exception:
                        await context.bot.send_message(
                            chat_id,
                            f"💐 {FLOWERS[flower_key]['name']} — к сожалению, не удалось отправить фото.",
                        )
                else:
                    await context.bot.send_message(
                        chat_id,
                        f"💐 Готовых букетов из {FLOWERS[flower_key]['name']} сейчас нет на фото.",
                    )
        ai_reply = re.sub(r"БУКЕТ:\S+", "", ai_reply).strip()

    # Отправляем текстовый ответ
    if ai_reply:
        reply_markup = _detect_inline_buttons(ai_reply)
        await context.bot.send_message(chat_id, ai_reply, reply_markup=reply_markup)

    await save_message(chat_id, "assistant", ai_reply)


def _detect_inline_buttons(ai_reply: str) -> InlineKeyboardMarkup | None:
    """Определяет нужны ли inline-кнопки по контексту ответа AI."""
    lower = ai_reply.lower()

    if "доставка или самовывоз" in lower or "доставку или самовывоз" in lower:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚚 Доставка", callback_data="delivery"),
                InlineKeyboardButton("📍 Самовывоз", callback_data="pickup"),
            ]
        ])

    if "способ оплаты" in lower or ("kaspi" in lower and "?" in ai_reply):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💳 Kaspi", callback_data="pay_Kaspi"),
                InlineKeyboardButton("💳 Kaspi Red", callback_data="pay_Kaspi_Red"),
                InlineKeyboardButton("📋 Рассрочка", callback_data="pay_Рассрочка"),
            ]
        ])

    if "стандартные или метровые" in lower or ("стандартн" in lower and "метров" in lower and "?" in ai_reply):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🌹 Стандартные (500 тг)", callback_data="flower_розы_стандартные"),
                InlineKeyboardButton("🌹 Метровые (1000 тг)", callback_data="flower_розы_метровые"),
            ]
        ])

    return None


async def _notify_admin(chat_id: int, order_data: dict | None, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет краткое уведомление владельцу о новом заказе."""
    if not ADMIN_CHAT_ID:
        print(f"[NOTIFY] ADMIN_CHAT_ID не задан", flush=True)
        return

    if order_data:
        flowers = order_data.get("flowers", "—")
        qty = order_data.get("quantity", "?")
        total = order_data.get("total_price", "?")
        name = order_data.get("customer_name", "—")
        phone = order_data.get("customer_phone", "—")
        date = order_data.get("pickup_date", "—")
        time = order_data.get("pickup_time", "")
        delivery = order_data.get("delivery_type", "")
        delivery_text = "Самовывоз" if delivery == "pickup" else "Доставка"
        address = order_data.get("delivery_address", "")
        payment = order_data.get("payment_method", "—")

        msg = (
            f"🔔 Новый заказ!\n\n"
            f"Цветы: {flowers} x {qty} шт\n"
            f"Сумма: {total} тг\n"
            f"Клиент: {name}\n"
            f"Тел: {phone}\n"
            f"Дата: {date} {time}\n"
            f"{delivery_text}"
        )
        if address:
            msg += f": {address}"
        msg += f"\nОплата: {payment}"
    else:
        msg = f"🔔 Новый заказ от клиента (chat_id: {chat_id})"

    print(f"[NOTIFY] Отправляю уведомление админу {ADMIN_CHAT_ID}...", flush=True)
    try:
        await context.bot.send_message(ADMIN_CHAT_ID, msg)
        print(f"[NOTIFY] Уведомление отправлено успешно", flush=True)
    except Exception as e:
        print(f"[NOTIFY] ОШИБКА отправки: {e}", flush=True)


# --- Напоминания ---

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    from database import get_upcoming_orders, mark_reminded

    orders = await get_upcoming_orders()

    for order in orders:
        chat_id = order.get("chat_id")
        order_id = order.get("id")
        pickup_date = order.get("pickup_date", "")
        pickup_time = order.get("pickup_time", "")

        if not chat_id or not pickup_date:
            continue

        flowers = order.get("flowers", "цветы")
        delivery = order.get("delivery_type", "")
        delivery_text = "самовывоз" if delivery == "pickup" else "доставка"

        try:
            await context.bot.send_message(
                chat_id,
                f"🔔 Напоминание! Ваш заказ ({flowers}) — {delivery_text} "
                f"{pickup_date} {pickup_time}.\n\n"
                f"Адрес самовывоза: {SHOP_ADDRESS}\n"
                f"Часы работы: {SHOP_HOURS}",
            )
            if order_id:
                await mark_reminded(order_id)
        except Exception:
            pass
