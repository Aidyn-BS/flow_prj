import re
from database import save_order, cancel_order, deduct_inventory, mark_bouquet_sold_for_flower
from catalog import find_flower_key


def parse_order_from_ai(ai_response: str, chat_id: int) -> dict | None:
    """Парсит подтверждённый заказ из ответа AI (триггер ЗАКАЗ_ПОДТВЕРЖДЁН)."""
    if "ЗАКАЗ_ПОДТВЕРЖДЁН" not in ai_response:
        return None

    # AI должен сформировать итог заказа в тексте — парсим основные поля
    order = {"chat_id": chat_id}

    # Извлекаем данные из текста ответа
    lines = ai_response.split("\n")
    for line in lines:
        line_lower = line.lower().strip()
        if any(w in line_lower for w in ["имя", "клиент"]):
            order["customer_name"] = _extract_value(line)
        elif any(w in line_lower for w in ["телефон", "номер"]):
            order["customer_phone"] = _extract_value(line)
        elif any(w in line_lower for w in ["цвет", "роз", "тюльпан", "пион"]):
            order["flowers"] = _extract_value(line)
        elif "кол" in line_lower or "шт" in line_lower:
            nums = re.findall(r"\d+", line)
            if nums:
                order["quantity"] = int(nums[0])
        elif any(w in line_lower for w in ["итого", "стоимость", "сумма", "цена"]):
            nums = re.findall(r"[\d\s]+", line)
            for n in nums:
                n_clean = n.replace(" ", "")
                if n_clean.isdigit() and int(n_clean) > 0:
                    order["total_price"] = int(n_clean)
                    break
        elif "доставк" in line_lower:
            order["delivery_type"] = "delivery"
            order["delivery_address"] = _extract_value(line)
        elif "самовывоз" in line_lower:
            order["delivery_type"] = "pickup"
        elif "дат" in line_lower or "когда" in line_lower:
            order["pickup_date"] = _extract_value(line)
        elif "врем" in line_lower:
            order["pickup_time"] = _extract_value(line)
        elif "оплат" in line_lower or "kaspi" in line_lower:
            order["payment_method"] = _extract_value(line)

    return order


def _extract_value(line: str) -> str:
    """Извлекает значение после двоеточия или тире."""
    for sep in [":", "—", "-", "–"]:
        if sep in line:
            return line.split(sep, 1)[1].strip()
    return line.strip()


async def process_order(ai_response: str, chat_id: int) -> str | None:
    """Обрабатывает ответ AI — сохраняет заказ если подтверждён."""
    if "ЗАКАЗ_ПОДТВЕРЖДЁН" in ai_response:
        order = parse_order_from_ai(ai_response, chat_id)
        if order:
            await save_order(order)

            # Вычитаем из инвентаря
            flowers_text = order.get("flowers", "")
            quantity = order.get("quantity", 0)
            flower_key = find_flower_key(flowers_text)
            if flower_key and quantity > 0:
                await deduct_inventory(flower_key, quantity)
                await mark_bouquet_sold_for_flower(flower_key)

            # Возвращаем текст без триггера
            return ai_response.replace("ЗАКАЗ_ПОДТВЕРЖДЁН", "").strip()
    elif "ЗАКАЗ_ОТМЕНЁН" in ai_response:
        await cancel_order(chat_id)
        return ai_response.replace("ЗАКАЗ_ОТМЕНЁН", "").strip()
    return None
