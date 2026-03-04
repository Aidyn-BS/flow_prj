import sys
import logging
import threading
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

# Логирование — всё пишется в stdout чтобы Amvera видел
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Сразу пишем что скрипт запустился
print("=== bot.py started ===", flush=True)

try:
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        filters,
    )
    print("=== telegram imported OK ===", flush=True)
except Exception as e:
    print(f"=== IMPORT ERROR telegram: {e} ===", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from config import TELEGRAM_BOT_TOKEN
    print(f"=== config loaded, token exists: {bool(TELEGRAM_BOT_TOKEN)} ===", flush=True)
except Exception as e:
    print(f"=== IMPORT ERROR config: {e} ===", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    from handlers import (
        start_handler,
        catalog_handler,
        message_handler,
        myorders_handler,
        stats_handler,
        admin_handler,
        inventory_handler,
        orders_handler,
        button_handler,
        photo_handler,
        document_handler,
        send_reminders,
    )
    print("=== handlers imported OK ===", flush=True)
except Exception as e:
    print(f"=== IMPORT ERROR handlers: {e} ===", flush=True)
    traceback.print_exc()
    sys.exit(1)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    try:
        server = HTTPServer(("0.0.0.0", 80), HealthHandler)
        print("=== Health server started on port 80 ===", flush=True)
        server.serve_forever()
    except Exception as e:
        print(f"=== Health server error: {e} ===", flush=True)


def main():
    print("=== main() called ===", flush=True)

    # Фоновый HTTP-сервер для healthcheck Amvera
    threading.Thread(target=start_health_server, daemon=True).start()

    try:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        print("=== Telegram app built OK ===", flush=True)
    except Exception as e:
        print(f"=== ERROR building app: {e} ===", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # Команды
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("catalog", catalog_handler))
    app.add_handler(CommandHandler("myorders", myorders_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("admin", admin_handler))
    app.add_handler(CommandHandler("inventory", inventory_handler))
    app.add_handler(CommandHandler("orders", orders_handler))

    # Inline-кнопки
    app.add_handler(CallbackQueryHandler(button_handler))

    # Фото (админ загружает фото цветов)
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Документы (webp и другие изображения отправленные как файл)
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Напоминания — каждый час проверяем заказы
    job_queue = app.job_queue
    job_queue.run_repeating(send_reminders, interval=3600, first=60)

    print("🌸 Rosa бот запущен!", flush=True)
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"=== FATAL ERROR: {e} ===", flush=True)
        traceback.print_exc()
        sys.exit(1)
