import aiohttp
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from prompts import build_system_prompt
from database import load_message_history, get_inventory_dict

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# История сообщений per chat_id (кэш в памяти)
chat_histories: dict[int, list[dict]] = {}


async def ensure_history_loaded(chat_id: int):
    """Загружает историю из Supabase если ещё не в кэше."""
    if chat_id not in chat_histories:
        history = await load_message_history(chat_id)
        chat_histories[chat_id] = history


def get_history(chat_id: int) -> list[dict]:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    return chat_histories[chat_id]


def add_message(chat_id: int, role: str, content: str):
    history = get_history(chat_id)
    history.append({"role": role, "content": content})
    if len(history) > 40:
        chat_histories[chat_id] = history[-30:]


def clear_history(chat_id: int):
    chat_histories.pop(chat_id, None)


async def get_ai_response(chat_id: int, user_message: str) -> str:
    # Подгружаем историю из БД если нет в памяти
    await ensure_history_loaded(chat_id)

    add_message(chat_id, "user", user_message)

    # Динамический промпт — разный для админа и клиента, включает текущий inventory
    inventory = await get_inventory_dict()
    system_prompt = build_system_prompt(chat_id, inventory)

    messages = [{"role": "system", "content": system_prompt}] + get_history(chat_id)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENROUTER_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    return f"Извините, произошла ошибка. Попробуйте позже. ({resp.status})"

                data = await resp.json()
                reply = data["choices"][0]["message"]["content"]
                add_message(chat_id, "assistant", reply)
                return reply
    except Exception as e:
        return "Извините, сервис временно недоступен. Попробуйте позже."
