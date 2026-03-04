import re
from database import save_order, cancel_order, deduct_inventory, mark_bouquet_sold_for_flower
from catalog import find_flower_key


def parse_order_from_ai(ai_response: str, chat_id: int) -> dict | None:
    """Парсит подтверждённый заказ из структурированного ответа AI."""
    if "ЗАКАЗ_ПОДТВЕРЖДЁН" not in ai_response:
        return None

    order = {"chat_id": chat_id}

    # Парсим поля формата "Ключ: значение"
    field_map = {
        "цветы": "flowers",
        "количество": "quantity",
        "сумма": "total_price",
        "доставка": "delivery_type",
        "адрес": "delivery_address",
        "дата": "pickup_date",
        "время": "pickup_time",
        "имя": "customer_name",
        "телефон": "customer_phone",
        "оплата": "payment_method",
    }

    lines = ai_response.split("\n")
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped or "ЗАКАЗ_ПОДТВЕРЖДЁН" in line_stripped:
            continue

        # Ищем формат "Ключ: значение"
        if ":" in line_stripped:
            key_part, value_part = line_stripped.split(":", 1)
            key_lower = key_part.strip().lower()
            value = value_part.strip()

            for ru_key, en_field in field_map.items():
                if ru_key in key_lower:
                    if en_field == "quantity":
                        nums = re.findall(r"\d+", value)
                        if nums:
                            order["quantity"] = int(nums[0])
                    elif en_field == "total_price":
                        nums = re.findall(r"[\d\s]+", value)
                        for n in nums:
                            n_clean = n.replace(" ", "")
                            if n_clean.isdigit() and int(n_clean) > 0:
                                order["total_price"] = int(n_clean)
                                break
                    elif en_field == "delivery_type":
                        if "самовывоз" in value.lower():
                            order["delivery_type"] = "pickup"
                        else:
                            order["delivery_type"] = "delivery"
                            order["delivery_address"] = value
                    else:
                        order[en_field] = value
                    break

    return order


def _get_clean_reply(ai_response: str) -> str:
    """Убирает триггер и структурированные поля, оставляет только текст для клиента."""
    lines = ai_response.split("\n")
    clean_lines = []
    field_keywords = ["цветы:", "количество:", "сумма:", "доставка:", "адрес:",
                      "дата:", "время:", "имя:", "телефон:", "оплата:"]

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        if "ЗАКАЗ_ПОДТВЕРЖДЁН" in line_stripped:
            continue
        # Пропускаем строки с полями заказа
        is_field = False
        for kw in field_keywords:
            if line_stripped.lower().startswith(kw):
                is_field = True
                break
        if not is_field:
            clean_lines.append(line_stripped)

    return "\n".join(clean_lines).strip()


async def process_order(ai_response: str, chat_id: int) -> str | None:
    """Обрабатывает ответ AI — сохраняет заказ если подтверждён."""
    if "ЗАКАЗ_ПОДТВЕРЖДЁН" in ai_response:
        order = parse_order_from_ai(ai_response, chat_id)
        if order:
            print(f"[ORDER] Parsed order: {order}", flush=True)
            await save_order(order)

            # Вычитаем из инвентаря
            flowers_text = order.get("flowers", "")
            quantity = order.get("quantity", 0)
            flower_key = find_flower_key(flowers_text)
            if flower_key and quantity > 0:
                await deduct_inventory(flower_key, quantity)
                await mark_bouquet_sold_for_flower(flower_key)

            # Возвращаем чистый текст без полей заказа
            clean = _get_clean_reply(ai_response)
            if not clean:
                clean = "Ваш заказ принят! Оператор свяжется с вами для оплаты."
            return clean
    elif "ЗАКАЗ_ОТМЕНЁН" in ai_response:
        await cancel_order(chat_id)
        return ai_response.replace("ЗАКАЗ_ОТМЕНЁН", "").strip()
    return None
