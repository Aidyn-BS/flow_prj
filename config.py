import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

SHOP_NAME = "Rosa"
SHOP_PHONE = "+7 707 285 3000"
SHOP_ADDRESS = "ул. Цветочная 77, Алматы"
SHOP_HOURS = "10:00–22:00 ежедневно"

# Chat ID владельца (или группы) для уведомлений о заказах
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
