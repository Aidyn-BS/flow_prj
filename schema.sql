-- ============================================
-- Rosa — полная очистка + создание таблиц
-- Вставь в Supabase → SQL Editor → Run
-- ============================================

-- Удаляем таблицы образовательного центра
DROP TABLE IF EXISTS admin_users CASCADE;
DROP TABLE IF EXISTS chat_history CASCADE;
DROP TABLE IF EXISTS telegram_users CASCADE;
DROP TABLE IF EXISTS trial_lessons CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Удаляем старые таблицы Rosa если есть
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS flower_photos CASCADE;

-- ============================================
-- Создаём таблицы Rosa
-- ============================================

CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    customer_name TEXT DEFAULT '',
    customer_phone TEXT DEFAULT '',
    flowers TEXT DEFAULT '',
    quantity INTEGER DEFAULT 0,
    total_price INTEGER DEFAULT 0,
    delivery_type TEXT DEFAULT '',
    delivery_address TEXT DEFAULT '',
    pickup_date TEXT DEFAULT '',
    pickup_time TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    status TEXT DEFAULT 'confirmed',
    reminded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Инвентарь цветов (количество на складе)
CREATE TABLE inventory (
    id BIGSERIAL PRIMARY KEY,
    flower_key TEXT NOT NULL UNIQUE,
    quantity INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Фото цветов (Telegram file_id)
-- photo_type: 'bouquet' = фото букета (удаляется после продажи), 'reference' = справочное фото (постоянное)
CREATE TABLE flower_photos (
    id BIGSERIAL PRIMARY KEY,
    flower_key TEXT NOT NULL,
    photo_type TEXT NOT NULL CHECK (photo_type IN ('bouquet', 'reference')),
    file_id TEXT NOT NULL,
    sold BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_orders_chat_id ON orders(chat_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_messages_chat_id ON messages(chat_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_inventory_flower ON inventory(flower_key);
CREATE INDEX idx_photos_flower ON flower_photos(flower_key);
CREATE INDEX idx_photos_type ON flower_photos(photo_type);

-- RLS
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE flower_photos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all" ON orders FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON messages FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON inventory FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all" ON flower_photos FOR ALL USING (true) WITH CHECK (true);
