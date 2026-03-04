from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import datetime, timedelta

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL и SUPABASE_KEY не заданы! "
        "Скопируйте .env.example в .env и заполните данные Supabase."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==================== ORDERS ====================

async def save_order(order_data: dict) -> dict:
    row = {
        "chat_id": order_data["chat_id"],
        "customer_name": order_data.get("customer_name", ""),
        "customer_phone": order_data.get("customer_phone", ""),
        "flowers": order_data.get("flowers", ""),
        "quantity": order_data.get("quantity", 0),
        "total_price": order_data.get("total_price", 0),
        "delivery_type": order_data.get("delivery_type", ""),
        "delivery_address": order_data.get("delivery_address", ""),
        "pickup_date": order_data.get("pickup_date", ""),
        "pickup_time": order_data.get("pickup_time", ""),
        "payment_method": order_data.get("payment_method", ""),
        "status": "confirmed",
        "reminded": False,
        "created_at": datetime.now().isoformat(),
    }
    result = supabase.table("orders").insert(row).execute()
    return result.data[0] if result.data else {}


async def cancel_order(chat_id: int) -> bool:
    result = (
        supabase.table("orders")
        .update({"status": "cancelled"})
        .eq("chat_id", chat_id)
        .eq("status", "confirmed")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return bool(result.data)


async def get_orders(chat_id: int) -> list:
    result = (
        supabase.table("orders")
        .select("*")
        .eq("chat_id", chat_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return result.data or []


async def get_all_orders(limit: int = 10) -> list:
    result = (
        supabase.table("orders")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


# ==================== MESSAGES ====================

async def save_message(chat_id: int, role: str, content: str):
    supabase.table("messages").insert({
        "chat_id": chat_id,
        "role": role,
        "content": content,
        "created_at": datetime.now().isoformat(),
    }).execute()


async def load_message_history(chat_id: int, limit: int = 30) -> list[dict]:
    result = (
        supabase.table("messages")
        .select("role, content")
        .eq("chat_id", chat_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    if not result.data:
        return []
    return list(reversed(result.data))


# ==================== STATS ====================

async def get_stats(period: str = "day") -> dict:
    now = datetime.now()
    if period == "day":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    else:
        since = now - timedelta(days=30)

    result = (
        supabase.table("orders")
        .select("*")
        .gte("created_at", since.isoformat())
        .execute()
    )
    orders = result.data or []

    confirmed = [o for o in orders if o.get("status") == "confirmed"]
    cancelled = [o for o in orders if o.get("status") == "cancelled"]
    total_revenue = sum(o.get("total_price", 0) for o in confirmed)

    flower_counts: dict[str, int] = {}
    for o in confirmed:
        f = o.get("flowers", "Неизвестно")
        flower_counts[f] = flower_counts.get(f, 0) + 1
    top_flowers = sorted(flower_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_orders": len(orders),
        "confirmed": len(confirmed),
        "cancelled": len(cancelled),
        "revenue": total_revenue,
        "top_flowers": top_flowers,
    }


# ==================== REMINDERS ====================

async def get_upcoming_orders() -> list:
    result = (
        supabase.table("orders")
        .select("*")
        .eq("status", "confirmed")
        .eq("reminded", False)
        .execute()
    )
    return result.data or []


async def mark_reminded(order_id: int):
    supabase.table("orders").update({"reminded": True}).eq("id", order_id).execute()


# ==================== INVENTORY ====================

async def get_inventory() -> list[dict]:
    result = supabase.table("inventory").select("*").execute()
    return result.data or []


async def get_inventory_dict() -> dict[str, int]:
    rows = await get_inventory()
    return {r["flower_key"]: r["quantity"] for r in rows}


async def update_inventory(flower_key: str, quantity_delta: int):
    existing = (
        supabase.table("inventory")
        .select("id, quantity")
        .eq("flower_key", flower_key)
        .execute()
    )
    if existing.data:
        row = existing.data[0]
        new_qty = max(0, row["quantity"] + quantity_delta)
        supabase.table("inventory").update({
            "quantity": new_qty,
            "updated_at": datetime.now().isoformat(),
        }).eq("id", row["id"]).execute()
    else:
        supabase.table("inventory").insert({
            "flower_key": flower_key,
            "quantity": max(0, quantity_delta),
            "updated_at": datetime.now().isoformat(),
        }).execute()


async def set_inventory(flower_key: str, quantity: int):
    """Устанавливает точное количество цветов (админ синхронизирует вручную)."""
    existing = (
        supabase.table("inventory")
        .select("id")
        .eq("flower_key", flower_key)
        .execute()
    )
    if existing.data:
        supabase.table("inventory").update({
            "quantity": max(0, quantity),
            "updated_at": datetime.now().isoformat(),
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("inventory").insert({
            "flower_key": flower_key,
            "quantity": max(0, quantity),
            "updated_at": datetime.now().isoformat(),
        }).execute()


async def deduct_inventory(flower_key: str, quantity: int):
    await update_inventory(flower_key, -quantity)


# ==================== FLOWER PHOTOS ====================

async def save_flower_photo(flower_key: str, photo_type: str, file_id: str):
    supabase.table("flower_photos").insert({
        "flower_key": flower_key,
        "photo_type": photo_type,
        "file_id": file_id,
        "sold": False,
        "created_at": datetime.now().isoformat(),
    }).execute()


async def get_flower_photos(flower_key: str, photo_type: str) -> list[dict]:
    query = (
        supabase.table("flower_photos")
        .select("*")
        .eq("flower_key", flower_key)
        .eq("photo_type", photo_type)
    )
    if photo_type == "bouquet":
        query = query.eq("sold", False)
    result = query.order("created_at", desc=True).execute()
    return result.data or []


async def mark_photo_sold(photo_id: int):
    supabase.table("flower_photos").update({"sold": True}).eq("id", photo_id).execute()


async def mark_bouquet_sold_for_flower(flower_key: str):
    photos = await get_flower_photos(flower_key, "bouquet")
    if photos:
        await mark_photo_sold(photos[0]["id"])
