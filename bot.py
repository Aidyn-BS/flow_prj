import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import TELEGRAM_BOT_TOKEN
from handlers import (
    start_handler,
    catalog_handler,
    message_handler,
    myorders_handler,
    stats_handler,
    admin_handler,
    inventory_handler,
    button_handler,
    photo_handler,
    document_handler,
    send_reminders,
)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # тихий лог


def start_health_server():
    server = HTTPServer(("0.0.0.0", 80), HealthHandler)
    server.serve_forever()


def main():
    # Фоновый HTTP-сервер для healthcheck Amvera
    threading.Thread(target=start_health_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("catalog", catalog_handler))
    app.add_handler(CommandHandler("myorders", myorders_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("admin", admin_handler))
    app.add_handler(CommandHandler("inventory", inventory_handler))

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

    print("🌸 Rosa бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
