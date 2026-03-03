FLOWERS = {
    "розы_стандартные": {
        "name": "Розы стандартные",
        "price": 500,
        "unit": "тг/шт",
        "description": "Классические розы для любого повода",
    },
    "розы_метровые": {
        "name": "Розы метровые",
        "price": 1000,
        "unit": "тг/шт",
        "description": "Метровые розы премиум-класса. От 10 шт — 900 тг/шт",
        "bulk_price": 900,
        "bulk_min": 10,
    },
    "тюльпаны": {
        "name": "Тюльпаны",
        "price": 100,
        "unit": "тг/шт",
        "description": "Лёгкие и яркие, символ весны",
    },
    "пионы": {
        "name": "Пионы",
        "price": 1500,
        "unit": "тг/шт",
        "description": "Пышные и романтичные, для особых случаев",
    },
    "ромашки": {
        "name": "Ромашки",
        "price": 200,
        "unit": "тг/шт",
        "description": "Нежные, про искренность и уют",
    },
    "хризантемы": {
        "name": "Хризантемы",
        "price": 400,
        "unit": "тг/шт",
        "description": "Стойкие, долго стоят в вазе",
    },
    "гортензии": {
        "name": "Гортензии",
        "price": 2000,
        "unit": "тг/шт",
        "description": "Объёмные шапки, эффектный акцент в букетах",
    },
}

DELIVERY_INFO = {
    "delivery": "По тарифам Яндекс Доставки, оплачивает клиент. От 50 000 тг — бесплатная доставка.",
    "pickup": "Бесплатно. Адрес: ул. Цветочная 77, Алматы. Ежедневно 10:00–22:00.",
}

PAYMENT_METHODS = ["Kaspi", "Kaspi Red", "Рассрочка"]


def get_catalog_text():
    lines = ["🌸 *Каталог цветов Rosa*\n"]
    for flower in FLOWERS.values():
        lines.append(f"• *{flower['name']}* — {flower['price']} {flower['unit']}")
        lines.append(f"  _{flower['description']}_\n")
    return "\n".join(lines)


def find_flower_key(text: str) -> str | None:
    text_lower = text.lower()
    keywords = {
        "розы_стандартные": ["стандартн", "обычн"],
        "розы_метровые": ["метров", "длинн"],
        "тюльпаны": ["тюльпан"],
        "пионы": ["пион"],
        "ромашки": ["ромашк"],
        "хризантемы": ["хризантем"],
        "гортензии": ["гортенз"],
    }
    for key, kws in keywords.items():
        for kw in kws:
            if kw in text_lower:
                return key
    if "роз" in text_lower:
        return "розы_стандартные"
    return None
