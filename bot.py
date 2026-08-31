# ===============================
# 0.0 إصلاح قاعدة البيانات - يجري تلقائياً
# ===============================

def fix_database():
    """يضيف الأعمدة المفقودة بدون أي تدخل منك"""
    import os
    import psycopg2
    from urllib.parse import urlparse
    
    # جلب رابط قاعدة البيانات
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("⚠️ No DATABASE_URL found, using SQLite")
        return
    
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    
    try:
        # تحليل الرابط
        parsed = urlparse(database_url)
        dbname = parsed.path[1:]
        user = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port or 5432
        
        # الاتصال بقاعدة البيانات مباشرة (بدون SQLAlchemy)
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # جلب الأعمدة الموجودة
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'players'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # الأعمدة المطلوبة
        required_columns = {
            'house_type': 'VARCHAR(255)',
            'in_nether': 'BOOLEAN DEFAULT FALSE',
            'temples_visited': 'INTEGER DEFAULT 0',
            'temple_cooldown': 'TIMESTAMP',
            'dragon_party': 'JSON DEFAULT \'[]\'',
        }
        
        # إضافة الأعمدة المفقودة
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                print(f"🔧 Adding column: {col_name}")
                cursor.execute(f"ALTER TABLE players ADD COLUMN {col_name} {col_type}")
                print(f"✅ Column {col_name} added!")
        
        cursor.close()
        conn.close()
        print("✅ Database fixed successfully!")
        
    except Exception as e:
        print(f"⚠️ Fix error: {e}")

# ===== تشغيل الإصلاح =====
fix_database()

# ===============================
# 0. PATCH لمشكلة Story - الحل النهائي
# ===============================

import sys
import warnings
warnings.filterwarnings("ignore")

# ===== Patch شامل =====
import telebot.types
import json

# 1. حذف Story إذا موجود
if hasattr(telebot.types, 'Story'):
    del telebot.types.Story
    print("✅ Removed Story class")

# 2. Patch لـ Message و Chat
try:
    # Patch Message
    if hasattr(telebot.types, 'Message'):
        original_message_init = telebot.types.Message.__init__
        
        def patched_message_init(self, *args, **kwargs):
            # تنظيف الحقول
            kwargs.pop('story', None)
            kwargs.pop('sender_chat', None)
            
            # تنظيف chat إذا كان موجود
            if 'chat' in kwargs and isinstance(kwargs['chat'], dict):
                kwargs['chat'].pop('story', None)
                kwargs['chat'].pop('sender_chat', None)
            
            return original_message_init(self, *args, **kwargs)
        
        telebot.types.Message.__init__ = patched_message_init
        print("✅ Message.__init__ patched!")
    
    # Patch Chat
    if hasattr(telebot.types, 'Chat'):
        original_chat_init = telebot.types.Chat.__init__
        
        def patched_chat_init(self, *args, **kwargs):
            kwargs.pop('story', None)
            kwargs.pop('sender_chat', None)
            return original_chat_init(self, *args, **kwargs)
        
        telebot.types.Chat.__init__ = patched_chat_init
        print("✅ Chat.__init__ patched!")
        
except Exception as e:
    print(f"⚠️ Patch warning: {e}")

print("✅ Story patch applied successfully!")

# ===============================
# المكتبات الأساسية
# ===============================

import os
import json
import random
import telebot
import logging
import time
from telebot import types
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from threading import Thread, Lock
from flask import Flask

# ===============================
# 0. نظام البناء (مُعدل مع تحسين عرض الوقت)
# ===============================

class BuildingSystem:
    BUILDING_STAGES = {
        "foundation": {
            "name": "🏗️ الأساس",
            "emoji": "🏗️",
            "resources": {"stone": 10, "oak_wood": 5},
            "time": 30,
            "next": "walls"
        },
        "walls": {
            "name": "🧱 الجدران",
            "emoji": "🧱",
            "resources": {"stone": 20, "oak_wood": 10, "iron_ore": 2},
            "time": 45,
            "next": "roof"
        },
        "roof": {
            "name": "🏠 السقف",
            "emoji": "🏠",
            "resources": {"oak_wood": 15, "stone": 10, "spruce_wood": 5},
            "time": 40,
            "next": "doors"
        },
        "doors": {
            "name": "🚪 الأبواب",
            "emoji": "🚪",
            "resources": {"oak_wood": 6, "iron_ore": 2, "crafting_table": 1},
            "time": 25,
            "next": "windows"
        },
        "windows": {
            "name": "🪟 النوافذ",
            "emoji": "🪟",
            "resources": {"glass": 8, "iron_ore": 2, "stone": 4},
            "time": 35,
            "next": "complete"
        }
    }
    
    HOUSE_TYPES = {
        "wooden": {
            "name": "بيت خشبي",
            "emoji": "🏠",
            "stages": ["foundation", "walls", "roof", "doors", "windows"],
            "resources": {
                "foundation": {"oak_wood": 10, "stone": 5},
                "walls": {"oak_wood": 20, "spruce_wood": 10},
                "roof": {"oak_wood": 15, "stone": 5},
                "doors": {"oak_wood": 6, "iron_ore": 1},
                "windows": {"glass": 4, "iron_ore": 1}
            },
            "bonus": {"health": 5, "hunger": 3}
        },
        "stone": {
            "name": "بيت حجري",
            "emoji": "🏰",
            "stages": ["foundation", "walls", "roof", "doors", "windows"],
            "resources": {
                "foundation": {"stone": 15, "iron_ore": 2},
                "walls": {"stone": 30, "iron_ore": 4},
                "roof": {"stone": 20, "oak_wood": 5},
                "doors": {"iron_ore": 4, "oak_wood": 3},
                "windows": {"glass": 6, "iron_ore": 2}
            },
            "bonus": {"health": 10, "defense": 5}
        },
        "mansion": {
            "name": "قصر فاخر",
            "emoji": "🏛️",
            "stages": ["foundation", "walls", "roof", "doors", "windows"],
            "resources": {
                "foundation": {"stone": 25, "iron_ore": 5, "diamond": 1},
                "walls": {"stone": 40, "gold_ore": 10, "diamond": 3},
                "roof": {"stone": 30, "diamond": 5, "gold_ore": 5},
                "doors": {"diamond": 3, "gold_ore": 5},
                "windows": {"glass": 10, "diamond": 2, "gold_ore": 3}
            },
            "bonus": {"health": 20, "defense": 15, "luck": 10}
        }
    }
    
    def __init__(self, session):
        self.session = session
        self.building_progress = {}
    
    def get_available_houses(self, player):
        available = []
        if player.level >= 1:
            available.append("wooden")
        if player.level >= 5:
            available.append("stone")
        if player.level >= 15:
            available.append("mansion")
        return available
    
    def get_house_info(self, house_type):
        return self.HOUSE_TYPES.get(house_type)
    
    def get_stage_info(self, stage_name):
        return self.BUILDING_STAGES.get(stage_name)
    
    def get_building_stages_info(self, house_type):
        house = self.HOUSE_TYPES.get(house_type)
        if not house:
            return None
        info = []
        for i, stage in enumerate(house["stages"]):
            stage_info = self.BUILDING_STAGES[stage]
            resources = house["resources"].get(stage, {})
            info.append({
                "stage": stage,
                "name": stage_info["name"],
                "emoji": stage_info["emoji"],
                "resources": resources,
                "time": stage_info["time"],
                "index": i
            })
        return info
    
    def can_build(self, player, house_type):
        house = self.HOUSE_TYPES.get(house_type)
        if not house:
            return False, "❌ نوع بيت غير معروف"
        first_stage = house["stages"][0]
        resources = house["resources"].get(first_stage, {})
        for item, amt in resources.items():
            if not player.has_item(item, amt):
                return False, f"❌ تحتاج {amt} من {item} للمرحلة الأولى"
        return True, "✅ يمكن البدء بالبناء"
    
    def start_building(self, player, house_type):
        can, msg = self.can_build(player, house_type)
        if not can:
            return False, msg
        house = self.HOUSE_TYPES[house_type]
        first_stage = house["stages"][0]
        resources = house["resources"][first_stage]
        for item, amt in resources.items():
            player.remove_item(item, amt)
        self.building_progress[player.user_id] = {
            "house_type": house_type,
            "current_stage": first_stage,
            "stage_index": 0,
            "started_at": datetime.utcnow(),
            "stages": house["stages"]
        }
        self.session.commit()
        return True, f"🏗️ بدأت بناء {house['name']}!\nالمرحلة: {self.BUILDING_STAGES[first_stage]['name']}\n⏳ انتظر {self.BUILDING_STAGES[first_stage]['time']} ثانية"
    
    def get_building_status(self, player):
        if player.user_id not in self.building_progress:
            return None
        progress = self.building_progress[player.user_id]
        current_stage = progress["current_stage"]
        stage_info = self.BUILDING_STAGES.get(current_stage)
        time_passed = (datetime.utcnow() - progress["started_at"]).total_seconds()
        time_needed = stage_info["time"]
        
        # حساب الوقت المتبقي بشكل دقيق
        time_left = max(0, int(time_needed - time_passed))
        progress_percent = min(100, int((time_passed / time_needed) * 100))
        
        # تحويل الوقت المتبقي إلى دقائق وثواني
        minutes = time_left // 60
        seconds = time_left % 60
        time_str = f"{minutes}د {seconds}ث" if minutes > 0 else f"{seconds}ث"
        
        return {
            "house_type": progress["house_type"],
            "house_name": self.HOUSE_TYPES[progress["house_type"]]["name"],
            "current_stage": current_stage,
            "stage_name": stage_info["name"],
            "progress": progress_percent,
            "time_left": time_left,
            "time_left_str": time_str,
            "is_complete": time_passed >= time_needed
        }
    
    def complete_stage(self, player):
        if player.user_id not in self.building_progress:
            return False, "❌ لا يوجد بناء قيد التنفيذ"
        progress = self.building_progress[player.user_id]
        status = self.get_building_status(player)
        if not status["is_complete"]:
            return False, f"⏳ انتظر {status['time_left']} ثانية لإكمال المرحلة"
        stage_index = progress["stage_index"]
        stages = progress["stages"]
        if stage_index + 1 >= len(stages):
            house = self.HOUSE_TYPES[progress["house_type"]]
            bonus = house["bonus"]
            player.max_health += bonus.get("health", 0)
            player.current_health += bonus.get("health", 0)
            player.strength += bonus.get("strength", 0)
            player.speed += bonus.get("speed", 0)
            player.luck += bonus.get("luck", 0)
            player.house_type = progress["house_type"]  # حفظ نوع المنزل
            del self.building_progress[player.user_id]
            self.session.commit()
            return True, f"🎉 اكتمل بناء {house['name']}!\n\nمكافآت:\n❤️ +{bonus.get('health', 0)} صحة\n🛡️ +{bonus.get('defense', 0)} دفاع\n🍀 +{bonus.get('luck', 0)} حظ"
        next_stage = stages[stage_index + 1]
        progress["current_stage"] = next_stage
        progress["stage_index"] = stage_index + 1
        progress["started_at"] = datetime.utcnow()
        house = self.HOUSE_TYPES[progress["house_type"]]
        resources = house["resources"].get(next_stage, {})
        for item, amt in resources.items():
            if not player.has_item(item, amt):
                return False, f"❌ ليس لديك موارد كافية للمرحلة التالية\nتحتاج: {item} x{amt}"
            player.remove_item(item, amt)
        stage_info = self.BUILDING_STAGES[next_stage]
        self.session.commit()
        return True, f"✅ اكتملت {self.BUILDING_STAGES[stages[stage_index]]['name']}!\n\n🏗️ المرحلة التالية: {stage_info['name']}\n⏳ انتظر {stage_info['time']} ثانية"

# ===============================
# 1. قاعدة البيانات
# ===============================

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, default="Player")
    
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    skill_points = Column(Integer, default=0)
    
    max_health = Column(Integer, default=20)
    current_health = Column(Integer, default=20)
    max_hunger = Column(Integer, default=20)
    current_hunger = Column(Integer, default=20)
    
    strength = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    endurance = Column(Integer, default=0)
    luck = Column(Integer, default=0)
    
    inventory = Column(Text, default=lambda: json.dumps({f"slot_{i}": None for i in range(36)}))
    equipment = Column(Text, default=lambda: json.dumps({"helmet": None, "chestplate": None, "leggings": None, "boots": None, "weapon": None, "shield": None}))
    
    current_area = Column(String, default="forest")
    last_action = Column(DateTime, default=datetime.utcnow)
    last_sleep = Column(DateTime, default=datetime.utcnow)
    status_effects = Column(JSON, default=list)
    is_exploring = Column(Boolean, default=False)
    explore_end_time = Column(DateTime, default=None)
    
    titles = Column(JSON, default=list)
    recipes_unlocked = Column(JSON, default=lambda: ["base"])
    defeated_ender_dragon = Column(Boolean, default=False)
    
    pet = Column(String, default=None)
    game_time = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    temples_visited = Column(Integer, default=0)
    temple_cooldown = Column(DateTime, default=datetime.utcnow)
    
    in_nether = Column(Boolean, default=False)
    
    # تخزين نوع المنزل
    house_type = Column(String, default=None)
    
    # للقتال الجماعي
    dragon_party = Column(JSON, default=list)
    
    def get_inv(self):
        if self.inventory is None:
            default = {f"slot_{i}": None for i in range(36)}
            self.inventory = json.dumps(default)
            return default
        try:
            return json.loads(self.inventory)
        except:
            default = {f"slot_{i}": None for i in range(36)}
            self.inventory = json.dumps(default)
            return default
    
    def save_inv(self, inv):
        self.inventory = json.dumps(inv, ensure_ascii=False)
    
    def get_equip(self):
        defaults = {"helmet": None, "chestplate": None, "leggings": None, "boots": None, "weapon": None, "shield": None}
        if self.equipment is None:
            return defaults.copy()
        try:
            data = json.loads(self.equipment) if isinstance(self.equipment, str) else self.equipment
            if isinstance(data, dict):
                for key in defaults:
                    if key not in data:
                        data[key] = None
                return data
        except:
            pass
        return defaults.copy()
    
    def save_equip(self, eq):
        defaults = {"helmet": None, "chestplate": None, "leggings": None, "boots": None, "weapon": None, "shield": None}
        if not isinstance(eq, dict):
            eq = defaults.copy()
        for key in defaults:
            if key not in eq:
                eq[key] = None
        self.equipment = json.dumps(eq, ensure_ascii=False)
    
    def has_item(self, item_name, amount=1):
        inv = self.get_inv()
        total = sum(slot.get("amount", 0) for slot in inv.values() if slot and slot.get("name") == item_name)
        return total >= amount
    
    def add_item(self, item_name, amount=1):
        inv = self.get_inv()
        remaining = amount
        for slot in inv.values():
            if slot and slot.get("name") == item_name and slot.get("amount", 0) < 64:
                space = 64 - slot["amount"]
                add = min(remaining, space)
                slot["amount"] += add
                remaining -= add
                if remaining <= 0:
                    self.save_inv(inv)
                    return True
        while remaining > 0:
            placed = False
            for i in range(36):
                key = f"slot_{i}"
                if inv.get(key) is None:
                    add = min(remaining, 64)
                    inv[key] = {"name": item_name, "amount": add}
                    remaining -= add
                    placed = True
                    break
            if not placed:
                self.save_inv(inv)
                return False
        self.save_inv(inv)
        return True
    
    def remove_item(self, item_name, amount=1):
        inv = self.get_inv()
        remaining = amount
        for key, slot in inv.items():
            if slot and slot.get("name") == item_name:
                current = slot.get("amount", 0)
                if current <= remaining:
                    remaining -= current
                    inv[key] = None
                else:
                    slot["amount"] -= remaining
                    remaining = 0
                if remaining <= 0:
                    self.save_inv(inv)
                    return True
        self.save_inv(inv)
        return remaining <= 0
    
    def delete_slot(self, slot_num):
        inv = self.get_inv()
        inv[f"slot_{slot_num}"] = None
        self.save_inv(inv)
    
    def can_sleep(self):
        return (datetime.utcnow() - self.last_sleep).total_seconds() >= 43200
    
    def advance_time(self, minutes=5):
        self.game_time = (self.game_time + minutes) % 240
        return self.get_time_of_day()
    
    def get_time_of_day(self):
        if self.game_time < 20:
            return "🌅 الفجر"
        elif self.game_time < 60:
            return "☀️ الصباح"
        elif self.game_time < 120:
            return "🌤️ الظهيرة"
        elif self.game_time < 140:
            return "🌅 الغروب"
        elif self.game_time < 180:
            return "🌆 المساء"
        else:
            return "🌙 الليل"
    
    def is_night(self):
        return self.game_time >= 180
    
    def add_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * 10:
            self.xp -= self.level * 10
            self.level += 1
            self.max_health += 1
            self.current_health = self.max_health
            if self.level % 5 == 0:
                self.skill_points += 1
        recipes = self.recipes_unlocked if isinstance(self.recipes_unlocked, list) else json.loads(self.recipes_unlocked or '["base"]')
        if self.level >= 2 and "level_2" not in recipes:
            recipes.append("level_2")
        if self.level >= 5 and "level_3" not in recipes:
            recipes.append("level_3")
        if self.level >= 10 and "level_4" not in recipes:
            recipes.append("level_4")
        if self.level >= 15 and "level_5" not in recipes:
            recipes.append("level_5")
        self.recipes_unlocked = recipes
        titles = self.titles if isinstance(self.titles, list) else json.loads(self.titles or '[]')
        titles_map = {10: "مبتدئ", 20: "مستكشف", 30: "محارب", 40: "صياد", 50: "بناء", 60: "ساحر", 70: "بطل", 80: "أسطورة"}
        for lvl, t in titles_map.items():
            if self.level >= lvl and t not in titles:
                titles.append(t)
        self.titles = titles

# ===============================
# 2. إعداد قاعدة البيانات
# ===============================

def get_database_url():
    url = os.getenv('DATABASE_URL')
    if not url:
        return 'sqlite:///mc.db'
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url

DATABASE_URL = get_database_url()

try:
    if 'sqlite' in DATABASE_URL:
        engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
    else:
        engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    print("✅ قاعدة بيانات متصلة بنجاح")
except Exception as e:
    print(f"❌ خطأ: {e}")
    DATABASE_URL = 'sqlite:///mc.db'
    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    print("✅ قاعدة بيانات SQLite جاهزة")

def get_player(session, user_id, username=None):
    try:
        player = session.query(Player).filter_by(user_id=user_id).first()
        if not player:
            player = Player(user_id=user_id, username=username or f"Player_{user_id}")
            session.add(player)
            session.commit()
            return player, True
        return player, False
    except Exception as e:
        session.rollback()
        print(f"⚠️ Error in get_player: {e}")
        # محاولة مرة ثانية بعد rollback
        player = session.query(Player).filter_by(user_id=user_id).first()
        if not player:
            player = Player(user_id=user_id, username=username or f"Player_{user_id}")
            session.add(player)
            session.commit()
            return player, True
        return player, False

# ===============================
# 3. بيانات العالم
# ===============================

class WorldData:
    @staticmethod
    def get_trees():
        return [
            {"name": "شجرة بلوط", "emoji": "🌳", "blocks": 8, "resources": [("oak_wood", 1)], "rare": ("apple", 1, 0.2), "break_time": 2},
            {"name": "شجرة تنوب", "emoji": "🌲", "blocks": 10, "resources": [("spruce_wood", 1)], "rare": ("mushroom", 1, 0.2), "break_time": 2},
            {"name": "شجرة بتولا", "emoji": "🪵", "blocks": 7, "resources": [("birch_wood", 1)], "rare": ("sap", 1, 0.15), "break_time": 2},
            {"name": "شجرة استوائية", "emoji": "🌴", "blocks": 12, "resources": [("jungle_wood", 1)], "rare": ("tropical_fruit", 1, 0.1), "break_time": 2.5},
        ]
    
    @staticmethod
    def get_rocks():
        return [
            {"name": "حجر عادي", "emoji": "🪨", "blocks": 6, "resources": [("stone", 1)], "break_time": 3},
            {"name": "حجر فحم", "emoji": "🖤", "blocks": 8, "resources": [("stone", 1), ("coal", 1)], "break_time": 3},
            {"name": "حجر حديد", "emoji": "⛏️", "blocks": 10, "resources": [("stone", 1), ("iron_ore", 1)], "break_time": 4},
            {"name": "حجر ذهب", "emoji": "✨", "blocks": 12, "resources": [("stone", 1), ("gold_ore", 1)], "rare": ("diamond", 1, 0.03), "break_time": 5},
            {"name": "حجر ألماس", "emoji": "💎", "blocks": 15, "resources": [("stone", 1), ("diamond", 1)], "rare": ("emerald", 1, 0.02), "break_time": 6},
        ]
    
    @staticmethod
    def get_animals():
        return {
            "بقرة 🐄": [("leather", 2), ("raw_beef", 3), ("milk", 1)],
            "خنزير 🐷": [("raw_pork", 3), ("bone", 2)],
            "دجاجة 🐔": [("raw_chicken", 2), ("feather", 3), ("egg", 2)],
            "غنم 🐑": [("wool", 3), ("raw_mutton", 2)],
            "حصان 🐴": [("saddle", 1), ("hoof", 2)],
            "ذئب 🐺": [("bone", 2)],
            "دب 🐻": [("bear_meat", 3), ("bear_pelt", 2)],
        }
    
    @staticmethod
    def get_enemies(is_night=False):
        if is_night:
            return [
                {"name": "زومبي", "emoji": "🧟", "hp": 15, "damage": 6, "xp": 12, "drops": [("rotten_flesh", 2, 0.6)]},
                {"name": "سكلتون", "emoji": "💀", "hp": 18, "damage": 8, "xp": 15, "drops": [("bone", 3, 0.7), ("arrow", 3, 0.5)]},
                {"name": "كريبر", "emoji": "💚", "hp": 22, "damage": 14, "xp": 22, "drops": [("gunpowder", 3, 0.8)], "special": "explode"},
                {"name": "زومبي حديدي", "emoji": "🧟‍♂️", "hp": 25, "damage": 10, "xp": 18, "drops": [("iron_ore", 2, 0.4)]},
                {"name": "غول", "emoji": "👹", "hp": 35, "damage": 16, "xp": 30, "drops": [("gold_ore", 3, 0.5), ("diamond", 1, 0.15)]},
            ]
        else:
            return [
                {"name": "ذئب", "emoji": "🐺", "hp": 10, "damage": 4, "xp": 6, "drops": [("bone", 2, 0.5)], "special": "tameable"},
                {"name": "دب", "emoji": "🐻", "hp": 25, "damage": 9, "xp": 18, "drops": [("bear_meat", 2, 0.8), ("bear_pelt", 1, 0.4)]},
                {"name": "عنكبوت", "emoji": "🕷️", "hp": 12, "damage": 5, "xp": 8, "drops": [("spider_silk", 2, 0.5), ("spider_eye", 1, 0.3)]},
            ]
    
    @staticmethod
    def get_random_event(is_night):
        if is_night:
            events = [
                {"type": "loot", "msg": "🌙 وجدت صندوقاً في الظلام!", "item": random.choice(["coal", "iron_ore", "gold_ore"]), "amount": random.randint(2, 4)},
                {"type": "loot", "msg": "🕯️ شعلة مشتعلة!", "item": "torch", "amount": random.randint(4, 8)},
            ]
        else:
            events = [
                {"type": "loot", "msg": "🎁 وجدت هدية على الأرض!", "item": random.choice(["apple", "bread", "coal", "feather"]), "amount": random.randint(2, 4)},
                {"type": "loot", "msg": "🍯 خلية نحل!", "item": "honey", "amount": random.randint(3, 6)},
            ]
        return random.choice(events) if random.random() < 0.25 else None
    
    @staticmethod
    def get_temple_events():
        return {
            "puzzles": [
                {"q": "ما هو الشيء الذي يمشي بلا أرجل ويطير بلا أجنحة؟", "a": "الوقت", "reward": "apple", "amount": 5},
                {"q": "ما هو الشيء الذي كلما زاد نقص؟", "a": "العمر", "reward": "gold_ore", "amount": 2},
                {"q": "ما هو الشيء الذي له عين ولا يرى؟", "a": "الإبرة", "reward": "diamond", "amount": 1},
                {"q": "ما هو الشيء الذي يأكل ولا يشبع؟", "a": "النار", "reward": "coal", "amount": 8},
            ],
            "monsters": [
                {"name": "حارس المعبد", "emoji": "🗿", "hp": 40, "damage": 12, "xp": 35, "drops": [("gold_ore", 5, 0.8), ("diamond", 2, 0.3)]},
                {"name": "عفريت المعبد", "emoji": "👿", "hp": 30, "damage": 15, "xp": 28, "drops": [("emerald", 3, 0.5), ("gold_ore", 4, 0.6)]},
                {"name": "تنين صغير", "emoji": "🐉", "hp": 50, "damage": 18, "xp": 45, "drops": [("diamond", 3, 0.4), ("gold_ore", 8, 0.7)]},
            ],
            "treasures": [
                {"item": "diamond", "amount": 3},
                {"item": "gold_ore", "amount": 8},
                {"item": "emerald", "amount": 5},
                {"item": "enchanted_book", "amount": 1},
            ]
        }

# ===============================
# 4. نظام التصنيع (معدل)
# ===============================

class CraftingSystem:
    RECIPES = {
        "base": [
            {"name": "ألواح خشب", "emoji": "🪵", "in": {"oak_wood": 1}, "out": {"wooden_planks": 4}, "xp": 1},
            {"name": "عصي", "emoji": "🥢", "in": {"wooden_planks": 2}, "out": {"sticks": 4}, "xp": 1},
            {"name": "طاولة تصنيع", "emoji": "🔨", "in": {"wooden_planks": 4}, "out": {"crafting_table": 1}, "xp": 2},
            {"name": "فرن", "emoji": "🔥", "in": {"stone": 8}, "out": {"furnace": 1}, "xp": 2},
        ],
        "level_2": [
            {"name": "فأس خشبي", "emoji": "🪓", "in": {"wooden_planks": 3, "sticks": 2}, "out": {"wooden_axe": 1}, "xp": 3},
            {"name": "سيف خشبي", "emoji": "🗡️", "in": {"wooden_planks": 2, "sticks": 1}, "out": {"wooden_sword": 1}, "xp": 3},
            {"name": "سياج", "emoji": "🚧", "in": {"sticks": 6}, "out": {"fence": 3}, "xp": 1},
            {"name": "باب خشبي", "emoji": "🚪", "in": {"wooden_planks": 6}, "out": {"wooden_door": 1}, "xp": 2},
            {"name": "خوذة خشبية", "emoji": "🪖", "in": {"wooden_planks": 5}, "out": {"wooden_helmet": 1}, "xp": 3},
            {"name": "صدرية خشبية", "emoji": "👕", "in": {"wooden_planks": 8}, "out": {"wooden_chestplate": 1}, "xp": 4},
        ],
        "level_3": [
            {"name": "فأس حجري", "emoji": "🪓", "in": {"stone": 3, "sticks": 2}, "out": {"stone_axe": 1}, "xp": 5},
            {"name": "سيف حجري", "emoji": "🗡️", "in": {"stone": 2, "sticks": 1}, "out": {"stone_sword": 1}, "xp": 5},
            {"name": "معول حجري", "emoji": "⛏️", "in": {"stone": 3, "sticks": 2}, "out": {"stone_pickaxe": 1}, "xp": 5},
            {"name": "خوذة حجرية", "emoji": "🪖", "in": {"stone": 5}, "out": {"stone_helmet": 1}, "xp": 5},
            {"name": "صدرية حجرية", "emoji": "👕", "in": {"stone": 8}, "out": {"stone_chestplate": 1}, "xp": 6},
            {"name": "خبز", "emoji": "🍞", "in": {"wheat": 3}, "out": {"bread": 1}, "xp": 2},
        ],
        "level_4": [
            {"name": "معول حديدي", "emoji": "⛏️", "in": {"iron_ore": 3, "sticks": 2}, "out": {"iron_pickaxe": 1}, "xp": 7},
            {"name": "سيف حديدي", "emoji": "🗡️", "in": {"iron_ore": 2, "sticks": 1}, "out": {"iron_sword": 1}, "xp": 8},
            {"name": "خوذة حديدية", "emoji": "🪖", "in": {"iron_ore": 5}, "out": {"iron_helmet": 1}, "xp": 8},
            {"name": "صدرية حديدية", "emoji": "👕", "in": {"iron_ore": 8}, "out": {"iron_chestplate": 1}, "xp": 10},
            {"name": "بنطلون حديدي", "emoji": "👖", "in": {"iron_ore": 7}, "out": {"iron_leggings": 1}, "xp": 9},
            {"name": "حذاء حديدي", "emoji": "👢", "in": {"iron_ore": 4}, "out": {"iron_boots": 1}, "xp": 7},
            {"name": "قوس", "emoji": "🏹", "in": {"sticks": 3, "spider_silk": 3}, "out": {"bow": 1}, "xp": 4},
            {"name": "جرعة شفاء", "emoji": "🧪", "in": {"sap": 2, "mushroom": 1}, "out": {"healing_potion": 1}, "xp": 8},
        ],
        "level_5": [
            {"name": "فأس ألماسي", "emoji": "🪓", "in": {"diamond": 3, "sticks": 2}, "out": {"diamond_axe": 1}, "xp": 12},
            {"name": "سيف ألماسي", "emoji": "🗡️", "in": {"diamond": 2, "sticks": 1}, "out": {"diamond_sword": 1}, "xp": 15},
            {"name": "معول ألماسي", "emoji": "⛏️", "in": {"diamond": 3, "sticks": 2}, "out": {"diamond_pickaxe": 1}, "xp": 12},
            {"name": "درع ناري", "emoji": "🔥", "in": {"fiery_coal": 5, "iron_ore": 8}, "out": {"fire_chestplate": 1}, "xp": 18},
            {"name": "عين الإندر", "emoji": "👁️", "in": {"ender_pearl": 1, "blaze_rod": 1}, "out": {"eye_of_ender": 1}, "xp": 10},
            {"name": "جناح طيران", "emoji": "🪽", "in": {"diamond": 1, "feather": 10}, "out": {"elytra": 1}, "xp": 25},
            {"name": "تفاح ذهبي", "emoji": "🍎", "in": {"apple": 1, "gold_ore": 8}, "out": {"golden_apple": 1}, "xp": 15},
            {"name": "خوذة ألماسية", "emoji": "🪖", "in": {"diamond": 5}, "out": {"diamond_helmet": 1}, "xp": 15},
            {"name": "صدرية ألماسية", "emoji": "👕", "in": {"diamond": 8}, "out": {"diamond_chestplate": 1}, "xp": 18},
            {"name": "بنطلون ألماسي", "emoji": "👖", "in": {"diamond": 7}, "out": {"diamond_leggings": 1}, "xp": 16},
            {"name": "حذاء ألماسي", "emoji": "👢", "in": {"diamond": 4}, "out": {"diamond_boots": 1}, "xp": 14},
        ]
    }
    
    FURNACE_RECIPES = {
        "iron_ore": {"out": "iron_ingot", "time": 5, "fuel": "coal", "fuel_amt": 1},
        "gold_ore": {"out": "gold_ingot", "time": 5, "fuel": "coal", "fuel_amt": 1},
        "stone": {"out": "smooth_stone", "time": 3, "fuel": "coal", "fuel_amt": 1},
        "raw_beef": {"out": "cooked_beef", "time": 3, "fuel": "coal", "fuel_amt": 1},
        "raw_chicken": {"out": "cooked_chicken", "time": 3, "fuel": "coal", "fuel_amt": 1},
        "raw_pork": {"out": "cooked_pork", "time": 3, "fuel": "coal", "fuel_amt": 1},
        "raw_mutton": {"out": "cooked_mutton", "time": 3, "fuel": "coal", "fuel_amt": 1},
    }
    
    @classmethod
    def get_recipes(cls, player):
        recipes = player.recipes_unlocked if isinstance(player.recipes_unlocked, list) else json.loads(player.recipes_unlocked or '["base"]')
        
        if "base" not in recipes:
            recipes.append("base")
        if player.level >= 2 and "level_2" not in recipes:
            recipes.append("level_2")
        if player.level >= 5 and "level_3" not in recipes:
            recipes.append("level_3")
        if player.level >= 10 and "level_4" not in recipes:
            recipes.append("level_4")
        if player.level >= 15 and "level_5" not in recipes:
            recipes.append("level_5")
        
        player.recipes_unlocked = recipes
        
        all_recipes = []
        for level in recipes:
            if level in cls.RECIPES:
                all_recipes.extend(cls.RECIPES[level])
        return all_recipes

    @classmethod
    def craft(cls, player, recipe):
        for item, amt in recipe["in"].items():
            if not player.has_item(item, amt):
                return False, f"❌ تحتاج {amt} من {item}"
        for item, amt in recipe["in"].items():
            player.remove_item(item, amt)
        for item, amt in recipe["out"].items():
            player.add_item(item, amt)
        player.add_xp(recipe["xp"])
        return True, f"✅ تم تصنيع {recipe['name']}! +{recipe['xp']}XP"
    
    @classmethod
    def furnace_smelt(cls, player, item_name):
        if item_name not in cls.FURNACE_RECIPES:
            return False, "❌ هذا العنصر لا يمكن صهره"
        if not player.has_item("furnace"):
            return False, "❌ تحتاج فرن للصهر!"
        recipe = cls.FURNACE_RECIPES[item_name]
        if not player.has_item(item_name):
            return False, f"❌ ليس لديك {item_name}"
        if not player.has_item(recipe["fuel"], recipe["fuel_amt"]):
            return False, f"❌ تحتاج {recipe['fuel']} x{recipe['fuel_amt']} كوقود"
        player.remove_item(item_name, 1)
        player.remove_item(recipe["fuel"], recipe["fuel_amt"])
        player.add_item(recipe["out"], 1)
        player.add_xp(3)
        return True, f"🔥 تم صهر {item_name} ← {recipe['out']}! +3XP"

# ===============================
# 5. نظام اللعبة (مُعدل)
# ===============================

class GameMechanics:
    COMBAT_WEAPONS = ["wooden_sword", "stone_sword", "iron_sword", "diamond_sword", "bow"]
    VALID_AXES = ["wooden_axe", "stone_axe", "iron_axe", "diamond_axe"]
    VALID_PICKAXES = ["stone_pickaxe", "iron_pickaxe", "diamond_pickaxe"]
    
    def __init__(self, session):
        self.session = session
    
    def is_combat_weapon(self, weapon):
        return weapon in self.COMBAT_WEAPONS
    
    def is_valid_axe(self, weapon):
        return weapon in self.VALID_AXES
    
    def is_valid_pickaxe(self, weapon):
        return weapon in self.VALID_PICKAXES
    
    def update_game_time(self, player):
        if player.last_action:
            minutes_passed = (datetime.utcnow() - player.last_action).total_seconds() / 60
            if minutes_passed > 5:
                steps = int(minutes_passed / 5)
                for _ in range(min(steps, 10)):
                    player.advance_time(5)
        player.last_action = datetime.utcnow()
        self.session.commit()
        return player.get_time_of_day()
    
    def get_tree_animation(self, total, left):
        percentage = (total - left) / total if total > 0 else 1
        if percentage < 0.2:
            trunk, leaves = "🟩🟩🟩🟩🟩", "🌿🌿🌿"
        elif percentage < 0.4:
            trunk, leaves = "🟩🟩🟩🟫🟫", "🌿🌿"
        elif percentage < 0.6:
            trunk, leaves = "🟩🟫🟫🟫🟫", "🌿"
        elif percentage < 0.8:
            trunk, leaves = "🟫🟫🟫🟫🟫", "🍂"
        else:
            trunk, leaves = "💨💨💨💨💨", "💥"
        return f"\n   {leaves}\n   {trunk}\n   {'🪓' if percentage < 0.9 else '✅'}\n"
    
    def get_rock_animation(self, total, left):
        percentage = (total - left) / total if total > 0 else 1
        if percentage < 0.2:
            state = "⬛⬛⬛⬛⬛"
        elif percentage < 0.4:
            state = "⬛⬛⬛⬜⬜"
        elif percentage < 0.6:
            state = "⬛⬜⬜⬜⬜"
        elif percentage < 0.8:
            state = "⬜⬜⬜⬜⬜"
        else:
            state = "💨💨💨💨💨"
        sparkles = "✨" if percentage > 0.5 else ""
        return f"\n   {sparkles}\n   {state}\n   {'⛏️' if percentage < 0.9 else '✅'}\n"
    
    def get_break_time(self, player, base_time):
        eq = player.get_equip()
        weapon = eq.get("weapon")
        tool_speed = {
            "wooden_axe": 0.8, "stone_axe": 0.6, "iron_axe": 0.4, "diamond_axe": 0.3,
            "stone_pickaxe": 0.6, "iron_pickaxe": 0.4, "diamond_pickaxe": 0.3,
            "diamond_sword": 0.5, "iron_sword": 0.7,
        }
        speed = tool_speed.get(weapon, 1.0)
        level_bonus = max(0.7, 1 - (player.level * 0.015))
        strength_bonus = max(0.85, 1 - (player.strength * 0.02))
        return max(0.5, base_time * speed * level_bonus * strength_bonus)
    
    def chop_block(self, player, tree):
        eq = player.get_equip()
        weapon = eq.get("weapon")
        has_axe = self.is_valid_axe(weapon)
        rewards = []
        resource_multiplier = max(0.4, 1 - (player.level * 0.01))
        bonus_multiplier = 1.5 if has_axe else 1
        for res, amt in tree["resources"]:
            if random.random() < 0.2:
                continue
            actual_amt = max(1, int(amt * resource_multiplier * bonus_multiplier))
            player.add_item(res, actual_amt)
            rewards.append(f"{res} x{actual_amt}")
        if tree.get("rare"):
            rare_res, rare_amt, prob = tree["rare"]
            if has_axe:
                prob = min(0.5, prob * 1.5)
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"✨ {rare_res} x{rare_amt}")
        hunger_cost = 1.5 if player.is_night() else 1
        if has_axe:
            hunger_cost *= 0.8
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if random.random() < 0.08 and not has_axe:
            player.current_health = max(0, player.current_health - 2)
            rewards.append("💔 جرحت يدك!")
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 3)
        xp_reward = 2 if player.is_night() else 1
        if has_axe:
            xp_reward += 1
        player.add_xp(xp_reward)
        self.session.commit()
        return {"rewards": rewards, "hunger": player.current_hunger, "health": player.current_health, "xp": xp_reward, "failed": False}
    
    def mine_block(self, player, rock):
        eq = player.get_equip()
        weapon = eq.get("weapon")
        has_pickaxe = self.is_valid_pickaxe(weapon)
        if not has_pickaxe:
            return {"rewards": ["❌ تحتاج معولاً لتكسير الحجر!"], "hunger": player.current_hunger, "health": player.current_health, "xp": 0, "failed": True}
        resource_multiplier = max(0.4, 1 - (player.level * 0.01))
        rewards = []
        for res, amt in rock["resources"]:
            if random.random() < 0.2:
                continue
            actual_amt = max(1, int(amt * resource_multiplier))
            player.add_item(res, actual_amt)
            rewards.append(f"{res} x{actual_amt}")
        if rock.get("rare"):
            rare_res, rare_amt, prob = rock["rare"]
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"💎 {rare_res} x{rare_amt}")
        hunger_cost = 1.5 if player.is_night() else 1
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if random.random() < 0.08:
            player.current_health = max(0, player.current_health - 2)
            rewards.append("💔 أصبت نفسك!")
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 3)
        xp_reward = 2 if player.is_night() else 1
        player.add_xp(xp_reward)
        self.session.commit()
        return {"rewards": rewards, "hunger": player.current_hunger, "health": player.current_health, "xp": xp_reward, "failed": False}
    
    def hunt_animal(self, player, animal_name):
        eq = player.get_equip()
        weapon = eq.get("weapon")
        if not weapon or not self.is_combat_weapon(weapon):
            return {"error": "❌ تحتاج سيفاً أو قوساً للصيد!\nاستخدم /equip iron_sword"}
        loot = WorldData.get_animals().get(animal_name)
        if not loot:
            return {"error": "حيوان غير معروف"}
        rewards = []
        for res, amt in loot:
            if random.random() < 0.2:
                continue
            bonus = random.randint(0, 1) if not player.is_night() else 0
            if "sword" in weapon:
                bonus += 1
            player.add_item(res, amt + bonus)
            rewards.append(f"{res} x{amt + bonus}")
        hunger_cost = 2 if player.is_night() else 1.5
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if random.random() < 0.15:
            player.current_health = max(0, player.current_health - 3)
            rewards.append("💔 جرحك الحيوان!")
        xp_reward = 5 if player.is_night() else 3
        if "diamond" in weapon:
            xp_reward += 2
        player.add_xp(xp_reward)
        self.session.commit()
        return {"animal": animal_name, "rewards": rewards}
    
    def calc_damage(self, player):
        dmg = 2
        eq = player.get_equip()
        w = eq.get("weapon")
        # تقليل ضرر السيوف
        weapon_dmg = {"wooden_sword": 4, "stone_sword": 6, "iron_sword": 9, "diamond_sword": 12, "bow": 3}
        if w in weapon_dmg:
            dmg += weapon_dmg[w]
        if player.pet == "wolf":
            dmg += 4
        if player.is_night():
            dmg = int(dmg * 0.85)
        return dmg + int(dmg * player.strength * 0.03)
    
    def calc_defense(self, player):
        defense = 0
        eq = player.get_equip()
        armor_values = {"diamond": 4, "fire": 5, "iron": 3, "stone": 2, "wooden": 1}
        for slot in ["helmet", "chestplate", "leggings", "boots"]:
            armor = eq.get(slot)
            if armor:
                for key, val in armor_values.items():
                    if key in str(armor):
                        defense += val
                        break
        if player.is_night():
            defense = int(defense * 0.8)
        return defense
    
    def respawn(self, player):
        player.current_health = player.max_health // 2
        player.current_hunger = 10
        player.current_area = "forest"
        player.is_exploring = False
        player.game_time = 0
        
        # 🔥 إصلاح: إذا مات في النذر، نخرجه من النذر
        if player.in_nether:
            player.in_nether = False
            print(f"✅ Player {player.user_id} was in Nether, respawned to overworld")
        
        self.session.commit()
    
    def eat(self, player, food):
        food_db = {
            "apple": 4, "bread": 5, "cooked_beef": 8, "tropical_fruit": 8,
            "honey": 6, "golden_apple": 8, "milk": 3, "egg": 1,
            "raw_beef": 2, "raw_chicken": 1, "cooked_chicken": 6, "cooked_pork": 7, "cooked_mutton": 6
        }
        if food not in food_db:
            return {"error": "طعام غير معروف"}
        if not player.has_item(food):
            return {"error": "لا تملك هذا الطعام"}
        player.remove_item(food)
        val = food_db[food]
        if player.is_night():
            val = int(val * 0.8)
        player.current_hunger = min(player.max_hunger, player.current_hunger + val)
        effects = []
        if food == "golden_apple":
            player.current_health = min(player.max_health, player.current_health + 6)
            effects.append("💚 تفاح ذهبي يشفي!")
        if "raw" in food and random.random() < 0.3:
            effects.append("⚠️ تسمم غذائي")
            player.current_health = max(0, player.current_health - 3)
        self.session.commit()
        return {"food": food, "hunger": val, "current": player.current_hunger, "effects": effects}
    
    def sleep(self, player):
        if not player.can_sleep():
            left = 12 - (datetime.utcnow() - player.last_sleep).seconds // 3600
            return {"error": f"⏳ انتظر {left} ساعات"}
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        player.last_sleep = datetime.utcnow()
        player.game_time = 0
        self.session.commit()
        return {"msg": "😴 نمت جيداً!", "hp": player.current_health, "hunger": player.current_hunger}

# ===============================
# 6. نظام القتال
# ===============================

class BattleSystem:
    def __init__(self, session):
        self.session = session
    
    def start_battle(self, player, enemy):
        return {
            'player_hp': player.current_health, 'player_max_hp': player.max_health,
            'enemy_hp': enemy['hp'], 'enemy_max_hp': enemy['hp'],
            'enemy': enemy, 'round': 0,
            'log': [f"⚔️ بدأ القتال مع {enemy['emoji']} {enemy['name']}!"],
            'player_defending': False, 'is_night': player.is_night(),
        }
    
    def player_attack(self, player, battle_data):
        enemy = battle_data['enemy']
        base_damage = player.strength + 2
        eq = player.get_equip()
        weapon = eq.get('weapon')
        weapon_dmg = {'wooden_sword': 4, 'stone_sword': 6, 'iron_sword': 9, 'diamond_sword': 12, 'bow': 3}
        base_damage += weapon_dmg.get(weapon, 1)
        if battle_data['is_night']:
            base_damage = int(base_damage * 0.8)
        if random.random() < 0.15 + (player.luck / 100):
            base_damage *= 2
            battle_data['log'].append("💥 ضربة حاسمة!")
        enemy_defense = random.randint(0, 2)
        final_damage = max(1, base_damage - enemy_defense)
        battle_data['enemy_hp'] = max(0, battle_data['enemy_hp'] - final_damage)
        battle_data['log'].append(f"🗡️ ضربت {enemy['name']} بـ {final_damage} ضرر")
        battle_data['player_defending'] = False
        return battle_data
    
    def player_defend(self, player, battle_data):
        shield = 5 if not battle_data['is_night'] else 3
        battle_data['player_defending'] = True
        battle_data['log'].append(f"🛡️ استعددت للدفاع (+{shield} درع)")
        return battle_data
    
    def enemy_turn(self, player, battle_data):
        enemy = battle_data['enemy']
        player_defense = gm.calc_defense(player)
        if battle_data['player_defending']:
            player_defense += 5
            if battle_data['is_night']:
                player_defense += 3
            battle_data['player_defending'] = False
        enemy_damage = enemy['damage']
        if battle_data['is_night']:
            enemy_damage = int(enemy_damage * 1.3)
        if battle_data['round'] > 3:
            enemy_damage = int(enemy_damage * (1 + battle_data['round'] * 0.05))
        if enemy.get('special') == 'explode' and random.random() < 0.3:
            enemy_damage *= 2
            battle_data['log'].append(f"💥 {enemy['name']} انفجر!")
        final_damage = max(0, enemy_damage - player_defense)
        if final_damage > 0:
            battle_data['player_hp'] = max(0, battle_data['player_hp'] - final_damage)
            battle_data['log'].append(f"💢 {enemy['name']} ضربك بـ {final_damage} ضرر")
        else:
            battle_data['log'].append(f"🛡️ تصديت لهجوم {enemy['name']}!")
        return battle_data
    
    def try_escape(self, player, battle_data):
        chance = 30 + player.speed
        if battle_data['is_night']:
            chance = int(chance * 0.6)
        if battle_data['round'] > 2:
            chance -= battle_data['round'] * 3
        chance = max(10, min(80, chance))
        if random.random() * 100 < chance:
            battle_data['log'].append("🏃 هربت بنجاح!")
            return True, battle_data
        else:
            battle_data['log'].append("🚫 فشلت في الهروب!")
            return False, battle_data
    
    def check_win(self, player, battle_data):
        if battle_data['enemy_hp'] <= 0:
            enemy = battle_data['enemy']
            xp_reward = enemy['xp']
            if battle_data['is_night']:
                xp_reward = int(xp_reward * 1.5)
            if battle_data['round'] > 5:
                xp_reward += battle_data['round']
            player.add_xp(xp_reward)
            drops_text = []
            for item, amt, prob in enemy.get('drops', []):
                if random.random() < prob:
                    bonus = random.randint(0, 1 + player.luck // 10)
                    if battle_data['is_night']:
                        bonus += 1
                    total = amt + bonus
                    player.add_item(item, total)
                    drops_text.append(f"{item} x{total}")
            battle_data['log'].append(f"🎉 انتصرت على {enemy['name']}!")
            battle_data['log'].append(f"⭐ +{xp_reward} XP")
            if drops_text:
                battle_data['log'].append(f"📦 {', '.join(drops_text)}")
            self.session.commit()
            return 'win', battle_data
        if battle_data['player_hp'] <= 0:
            battle_data['log'].append("💀 لقد مت!")
            return 'dead', battle_data
        return None, battle_data

# ===============================
# 7. نظام المعبد (مُعدل)
# ===============================

class TempleSystem:
    def __init__(self, session):
        self.session = session
        self.temple_active = {}
    
    def enter_temple(self, player):
        if player.temple_cooldown and (datetime.utcnow() - player.temple_cooldown).total_seconds() < 3600:
            remaining = int(3600 - (datetime.utcnow() - player.temple_cooldown).total_seconds())
            return False, f"⏳ المعبد مغلق! انتظر {remaining//60} دقيقة"
        events = WorldData.get_temple_events()
        choice = random.random()
        if choice < 0.3:
            return "puzzle", random.choice(events["puzzles"])
        elif choice < 0.6:
            return "monster", random.choice(events["monsters"])
        else:
            return "treasure", random.choice(events["treasures"])
    
    def solve_puzzle(self, player, puzzle, answer):
        if answer.lower().strip() == puzzle["a"].lower():
            player.add_item(puzzle["reward"], puzzle["amount"])
            player.add_xp(10)
            player.temples_visited = (player.temples_visited or 0) + 1
            player.temple_cooldown = datetime.utcnow()
            self.session.commit()
            return True, f"✅ إجابة صحيحة! حصلت على {puzzle['reward']} x{puzzle['amount']} +10XP"
        else:
            damage = random.randint(3, 8)
            player.current_health = max(0, player.current_health - damage)
            self.session.commit()
            return False, f"❌ إجابة خاطئة! تأذيت بـ {damage} ضرر"
    
    def get_temple_reward(self, player, treasure):
        player.add_item(treasure["item"], treasure["amount"])
        player.add_xp(15)
        player.temples_visited = (player.temples_visited or 0) + 1
        player.temple_cooldown = datetime.utcnow()
        self.session.commit()
        return f"🎁 وجدت كنزاً! {treasure['item']} x{treasure['amount']} +15XP"
    
    def get_temple_menu(self):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🔍 استكشاف", callback_data="temple_explore"),
            types.InlineKeyboardButton("🚪 خروج", callback_data="temple_leave")
        )
        return kb

# ===============================
# 8. نظام التنين المتطور 🐉💪
# ===============================

class EnderDragonSystem:
    def __init__(self, session):
        self.session = session
        self.dragon_active = False
        self.dragon_hp = 0
        self.dragon_max_hp = 300  # 🔥 أقوى بثلاث مرات!
        self.dragon_phase = 1  # 1-3 مراحل
        self.crystals = []  # أبراج البلورات
        self.fighters = {}  # {user_id: {"damage": 0, "crystals_broken": 0}}
        self.dragon_spawn_time = None
        self.fight_lock = Lock()
        self.attack_cooldown = {}
        
        # أنماط هجوم التنين
        self.ATTACK_PATTERNS = {
            "fire_breath": {"damage": 20, "cooldown": 3, "emoji": "🔥", "name": "أنفاس النار"},
            "dive_bomb": {"damage": 30, "cooldown": 5, "emoji": "💨", "name": "انقضاض جوي"},
            "summon_minions": {"damage": 10, "cooldown": 8, "emoji": "👾", "name": "استدعاء حلفاء"},
            "ender_blast": {"damage": 40, "cooldown": 6, "emoji": "💜", "name": "انفجار الإندر"},
            "tail_whip": {"damage": 25, "cooldown": 4, "emoji": "🦎", "name": "صفعة الذيل"},
            "crystal_beam": {"damage": 35, "cooldown": 7, "emoji": "💎", "name": "شعاع البلورة"},
            "soul_fire": {"damage": 28, "cooldown": 5, "emoji": "💀", "name": "نار الروح"},
            "ender_storm": {"damage": 45, "cooldown": 9, "emoji": "🌀", "name": "عاصفة الإندر"},
        }
    
    def can_fight_dragon(self, player):
        if player.level < 20:
            return False, "❌ تحتاج مستوى 20 لمواجهة التنين!"
        if not player.has_item("eye_of_ender", 3):
            return False, "❌ تحتاج 3 عيون إندر لفتح البوابة!"
        if not player.has_item("diamond_sword") and not player.has_item("bow"):
            return False, "❌ تحتاج سيفاً ألماسياً أو قوساً لمواجهة التنين!"
        if player.defeated_ender_dragon:
            return False, "✅ لقد هزمت التنين بالفعل!"
        return True, "✅ جاهز لمواجهة التنين!"
    
    def start_dragon_fight(self, player):
        can, msg = self.can_fight_dragon(player)
        if not can:
            return False, msg
        
        with self.fight_lock:
            # خصم العيون
            player.remove_item("eye_of_ender", 3)
            
            # بدء المعركة
            self.dragon_active = True
            self.dragon_hp = self.dragon_max_hp
            self.dragon_phase = 1
            self.dragon_spawn_time = datetime.utcnow()
            
            # إنشاء 4 أبراج بلورات (يجب كسرها بالقوس)
            self.crystals = [
                {"id": i, "hp": 30, "x": (i-2)*20, "z": (i%2)*20, "active": True, "armor": 5}
                for i in range(4)
            ]
            
            # تسجيل المقاتل
            self.fighters[player.user_id] = {
                "damage": 0, 
                "crystals_broken": 0,
                "joined_at": datetime.utcnow(),
                "healing_done": 0
            }
            
            self.session.commit()
        
        return True, self.get_fight_status(player)
    
    def get_fight_status(self, player=None):
        """الحصول على حالة المعركة الحالية"""
        if not self.dragon_active:
            return "🐉 التنين في سبات عميق..."
        
        active_crystals = sum(1 for c in self.crystals if c["active"])
        players_count = len(self.fighters)
        
        # حساب الضرر الكلي للمقاتلين
        total_damage = sum(f["damage"] for f in self.fighters.values())
        
        # تحديد المرحلة
        hp_percent = (self.dragon_hp / self.dragon_max_hp) * 100
        if hp_percent < 30:
            phase_text = "💢 **المرحلة 3 - غضب التنين!**"
        elif hp_percent < 70:
            phase_text = "⚔️ **المرحلة 2 - معركة شرسة!**"
        else:
            phase_text = "🌟 **المرحلة 1 - بداية القتال**"
        
        # عرض حالة المقاتل إن وجد
        player_status = ""
        if player and player.user_id in self.fighters:
            f = self.fighters[player.user_id]
            player_status = f"\n\n👤 **أنت:**\n🗡️ ضررك: {f['damage']}\n💎 كسرت: {f['crystals_broken']} أبراج"
        
        return f"""🐉 **معركة تنين الإندر!**

{phase_text}

❤️ صحة التنين: {self.dragon_hp}/{self.dragon_max_hp} ({hp_percent:.1f}%)
💎 الأبراج النشطة: {active_crystals}/4
👥 المقاتلون: {players_count}
⏳ الوقت: {int((datetime.utcnow() - self.dragon_spawn_time).total_seconds() / 60)} دقيقة
📊 إجمالي الضرر: {total_damage}
{player_status}

⚔️ **الأوامر:**
• /dragon_attack - هجوم بالسيف
• /dragon_shot - إطلاق سهم (للكسر الأبراج)
• /dragon_crystal [رقم] - استهداف برج (1-4)
• /dragon_heal - استخدام جرعة شفاء
• /dragon_join - الانضمام للمعركة
• /dragon_status - تحديث الحالة"""
    
    def player_attack_sword(self, player):
        """هجوم بالسيف على التنين"""
        if not self.dragon_active:
            return False, "❌ لا يوجد تنين!"
        
        if not player.has_item("diamond_sword"):
            return False, "❌ تحتاج سيفاً ألماسياً للهجوم!"
        
        # حساب الضرر
        base_damage = 8 + player.strength
        base_damage += random.randint(5, 12)
        
        # مكافأة الصدرية النارية
        eq = player.get_equip()
        if eq.get("chestplate") == "fire_chestplate":
            base_damage += 5
        
        # ضربة حاسمة
        if random.random() < 0.2 + (player.luck / 100):
            base_damage = int(base_damage * 2.5)
            crit_msg = "💥 **ضربة حاسمة!**"
        else:
            crit_msg = ""
        
        # خصم الصحة
        self.dragon_hp = max(0, self.dragon_hp - base_damage)
        
        # تسجيل الضرر
        if player.user_id in self.fighters:
            self.fighters[player.user_id]["damage"] += base_damage
        
        # التنين يرد
        dragon_response = self.dragon_turn(player)
        
        self.session.commit()
        
        # التحقق من الفوز
        if self.dragon_hp <= 0:
            return self.dragon_defeated(player)
        
        # التحقق من المرحلة
        self.check_phase()
        
        response = f"⚔️ **هجوم بالسيف!**\n"
        if crit_msg:
            response += f"{crit_msg}\n"
        response += f"💔 -{base_damage} صحة للتنين!\n\n"
        response += dragon_response
        
        return True, response
    
    def player_shoot_bow(self, player):
        """إطلاق سهم - لكسر الأبراج أو إيذاء التنين"""
        if not self.dragon_active:
            return False, "❌ لا يوجد تنين!"
        
        if not player.has_item("bow"):
            return False, "❌ تحتاج قوساً!"
        
        if not player.has_item("arrow", 1):
            return False, "❌ ليس لديك سهام!"
        
        player.remove_item("arrow", 1)
        
        # اختيار الهدف
        active_crystals = [c for c in self.crystals if c["active"]]
        
        if active_crystals and random.random() < 0.6:
            # استهدف برج
            crystal = random.choice(active_crystals)
            damage = random.randint(10, 20)
            crystal["hp"] -= damage
            
            if crystal["hp"] <= 0:
                crystal["active"] = False
                self.dragon_hp = max(0, self.dragon_hp - 30)
                
                if player.user_id in self.fighters:
                    self.fighters[player.user_id]["crystals_broken"] += 1
                
                self.session.commit()
                return True, f"🏹 **أصبت البرج #{crystal['id']+1}!**\n💥 تدمير البرج!\n🐉 التنين يفقد 30 صحة!"
            else:
                self.session.commit()
                return True, f"🏹 **أصبت البرج #{crystal['id']+1}!**\n💔 -{damage} صحة للبرج\n📊 متبقي: {crystal['hp']}/30"
        else:
            # استهدف التنين
            damage = random.randint(5, 15)
            if random.random() < 0.15:
                damage = int(damage * 2)
                self.session.commit()
                return True, f"🏹 **سهم حاسم!**\n💔 -{damage} صحة للتنين!"
            
            self.dragon_hp = max(0, self.dragon_hp - damage)
            
            if player.user_id in self.fighters:
                self.fighters[player.user_id]["damage"] += damage
            
            self.session.commit()
            
            if self.dragon_hp <= 0:
                return self.dragon_defeated(player)
            
            return True, f"🏹 **سهم!**\n💔 -{damage} صحة للتنين!"
    
    def destroy_crystal(self, player, crystal_id):
        """تدمير برج معين"""
        if not self.dragon_active:
            return False, "❌ لا يوجد تنين!"
        
        if crystal_id < 1 or crystal_id > 4:
            return False, "❌ رقم البرج غير صحيح (1-4)"
        
        crystal = self.crystals[crystal_id - 1]
        if not crystal["active"]:
            return False, f"❌ البرج #{crystal_id} مدمر بالفعل!"
        
        if not player.has_item("bow"):
            return False, "❌ تحتاج قوساً لتدمير البرج!"
        
        if not player.has_item("arrow", 1):
            return False, "❌ ليس لديك سهام!"
        
        player.remove_item("arrow", 1)
        
        # تدمير البرج
        crystal["active"] = False
        self.dragon_hp = max(0, self.dragon_hp - 30)
        
        if player.user_id in self.fighters:
            self.fighters[player.user_id]["crystals_broken"] += 1
        
        # ضرر ارتدادي
        damage = random.randint(5, 15)
        player.current_health = max(0, player.current_health - damage)
        
        self.session.commit()
        
        if self.dragon_hp <= 0:
            return self.dragon_defeated(player)
        
        return True, f"💎 **تم تدمير البرج #{crystal_id}!**\n💥 -30 صحة للتنين!\n💔 ضرر ارتدادي: -{damage} صحة لك!"
    
    def player_heal(self, player):
        """استخدام جرعة شفاء"""
        if not self.dragon_active:
            return False, "❌ لا يوجد تنين!"
        
        if not player.has_item("healing_potion", 1):
            return False, "❌ ليس لديك جرعة شفاء!"
        
        player.remove_item("healing_potion", 1)
        heal_amount = random.randint(15, 25)
        player.current_health = min(player.max_health, player.current_health + heal_amount)
        
        if player.user_id in self.fighters:
            self.fighters[player.user_id]["healing_done"] += heal_amount
        
        self.session.commit()
        
        return True, f"🧪 **استخدمت جرعة شفاء!**\n❤️ +{heal_amount} صحة!"
    
    def dragon_turn(self, player):
        """دور التنين - هجوم ذكي مع تطور المراحل"""
        if not self.dragon_active or self.dragon_hp <= 0:
            return "🐉 التنين سقط!"
        
        hp_percent = (self.dragon_hp / self.dragon_max_hp) * 100
        
        # اختيار الهجمات حسب المرحلة
        if hp_percent > 70:
            available_attacks = ["fire_breath", "tail_whip", "crystal_beam"]
        elif hp_percent > 30:
            available_attacks = ["fire_breath", "dive_bomb", "summon_minions", "soul_fire"]
        else:
            available_attacks = ["ender_blast", "dive_bomb", "ender_storm", "summon_minions"]
        
        # اختيار هجوم عشوائي مع مراعاة التبريد
        attack_name = random.choice(available_attacks)
        attack = self.ATTACK_PATTERNS[attack_name]
        
        # حساب الضرر النهائي
        base_damage = attack["damage"]
        
        # في المرحلة 3 (أقل من 30%)، الضرر أكبر
        if hp_percent < 30:
            base_damage = int(base_damage * 1.8)
            phase_text = "💢 **غضب التنين!** "
        elif hp_percent < 70:
            base_damage = int(base_damage * 1.3)
            phase_text = "⚔️ "
        else:
            phase_text = ""
        
        # حساب دفاع اللاعب
        player_defense = gm.calc_defense(player)
        final_damage = max(5, base_damage - player_defense//2)
        
        # تطبيق الضرر
        player.current_health = max(0, player.current_health - final_damage)
        self.session.commit()
        
        # رسائل خاصة
        special_messages = {
            "fire_breath": "🔥 التنين ينفث النار!",
            "dive_bomb": "💨 التنين ينقض من الأعلى!",
            "summon_minions": "👾 التنين يستدعي حلفاءه!",
            "ender_blast": "💜 انفجار طاقة الإندر!",
            "tail_whip": "🦎 التنين يضرب بذيله!",
            "crystal_beam": "💎 شعاع من البلورات!",
            "soul_fire": "💀 نار الروح تحرقك!",
            "ender_storm": "🌀 عاصفة الإندر تجتاح!"
        }
        
        response = f"{phase_text}{special_messages.get(attack_name, attack['emoji'] + ' ' + attack['name'])}\n"
        response += f"💔 -{final_damage} صحة لك!\n"
        
        # إضافة تأثيرات خاصة
        if attack_name == "summon_minions":
            minions = ["إندر مان", "سكلتون ناري", "زلزال ناري"]
            summoned = random.sample(minions, random.randint(1, 2))
            response += f"👾 استدعى: {', '.join(summoned)}!\n"
            # ضرر إضافي من الحلفاء
            extra_damage = random.randint(5, 10)
            player.current_health = max(0, player.current_health - extra_damage)
            response += f"💔 هجوم الحلفاء: -{extra_damage} صحة!"
            self.session.commit()
        
        if attack_name == "ender_storm":
            # تأثير عاصفة الإندر - يقلل الجوع
            player.current_hunger = max(0, player.current_hunger - 3)
            response += f"🍖 العاصفة استنزفت جوعك!"
            self.session.commit()
        
        return response
    
    def check_phase(self):
        """تحديث المرحلة حسب الصحة المتبقية"""
        hp_percent = (self.dragon_hp / self.dragon_max_hp) * 100
        if hp_percent < 30:
            self.dragon_phase = 3
        elif hp_percent < 70:
            self.dragon_phase = 2
        else:
            self.dragon_phase = 1
    
    def dragon_defeated(self, player):
        """معركة التنين - الفوز"""
        self.dragon_active = False
        player.defeated_ender_dragon = True
        
        # مكافآت ضخمة
        xp_bonus = 200
        level_bonus = 3
        
        player.add_xp(xp_bonus)
        player.level += level_bonus
        
        # مكافآت خاصة
        rewards = [
            ("diamond", 15),
            ("gold_ore", 30),
            ("ender_pearl", 8),
            ("dragon_head", 1),
            ("dragon_egg", 1),
            ("netherite_scrap", 5),
            ("enchanted_book", 2)
        ]
        
        rewards_text = []
        for item, amt in rewards:
            player.add_item(item, amt)
            rewards_text.append(f"{item} x{amt}")
        
        # لقب جديد
        titles = player.titles if isinstance(player.titles, list) else json.loads(player.titles or '[]')
        if "🏆 قاتل التنين" not in titles:
            titles.append("🏆 قاتل التنين")
        player.titles = titles
        
        self.session.commit()
        
        # حساب إحصائيات المعركة
        total_damage = sum(f["damage"] for f in self.fighters.values())
        total_crystals = sum(f["crystals_broken"] for f in self.fighters.values())
        
        return True, f"""🎉 **لقد هزمت تنين الإندر!**

⭐ **المكافآت:**
• +{xp_bonus} XP
• +{level_bonus} مستويات

🎁 **الغنائم:**
{chr(10).join(rewards_text)}

🏅 **لقب جديد:** 🏆 قاتل التنين

📊 **إحصائيات المعركة:**
🗡️ إجمالي الضرر: {total_damage}
💎 الأبراج المدمرة: {total_crystals}
👥 المشاركون: {len(self.fighters)}

**تهانينا! أنت أسطورة ماينكرافت!** 🐉👑"""
    
    def join_fight(self, player):
        """انضمام لاعب جديد للمعركة"""
        if not self.dragon_active:
            return False, "❌ لا توجد معركة نشطة!"
        
        if player.user_id in self.fighters:
            return False, "⚠️ أنت بالفعل في المعركة!"
        
        if player.level < 20:
            return False, "❌ تحتاج مستوى 20!"
        
        if not player.has_item("diamond_sword") and not player.has_item("bow"):
            return False, "❌ تحتاج سيفاً ألماسياً أو قوساً!"
        
        self.fighters[player.user_id] = {
            "damage": 0,
            "crystals_broken": 0,
            "joined_at": datetime.utcnow(),
            "healing_done": 0
        }
        
        self.session.commit()
        return True, f"👤 انضممت للمعركة!\n🐉 صحة التنين: {self.dragon_hp}/{self.dragon_max_hp}"

# ===============================
# 9. نظام النذر (مُعدل)
# ===============================

class NetherSystem:
    NETHER_ITEMS = {
        "nether_wart": {"name": "نتي وارت", "emoji": "🌿"},
        "blaze_rod": {"name": "عصا البلاز", "emoji": "🔥"},
        "ghast_tear": {"name": "دمعة الغاست", "emoji": "💧"},
        "magma_cream": {"name": "كريم الماجما", "emoji": "🟠"},
        "netherite_scrap": {"name": "خردة النذريت", "emoji": "⚫"},
        "gold_ore": {"name": "ذهب خام", "emoji": "✨"},
        "soul_sand": {"name": "رمل الروح", "emoji": "🟤"},
        "nether_brick": {"name": "طوب الجحيم", "emoji": "🧱"},
    }
    
    # أعداء النذر (أقوى)
    NETHER_MOBS = [
        {"name": "بلاز", "emoji": "🔥", "hp": 35, "damage": 14, "xp": 25, 
         "drops": [("blaze_rod", 2, 0.7), ("fiery_coal", 1, 0.3)]},
        {"name": "غاست", "emoji": "👻", "hp": 45, "damage": 20, "xp": 35,
         "drops": [("ghast_tear", 1, 0.4), ("gunpowder", 4, 0.6)]},
        {"name": "بيغ زومبي", "emoji": "🧟‍♂️", "hp": 40, "damage": 16, "xp": 30,
         "drops": [("gold_ore", 3, 0.6), ("rotten_flesh", 5, 0.8)]},
        {"name": "سكلتون الجحيم", "emoji": "💀", "hp": 30, "damage": 18, "xp": 25,
         "drops": [("nether_brick", 4, 0.7), ("bow", 1, 0.1)]},
        {"name": "ماغما كيوب", "emoji": "🟠", "hp": 25, "damage": 12, "xp": 20,
         "drops": [("magma_cream", 2, 0.6), ("fiery_coal", 1, 0.2)]},
        {"name": "بيدرازين (زعيم)", "emoji": "👾", "hp": 70, "damage": 28, "xp": 55,
         "drops": [("netherite_scrap", 2, 0.5), ("diamond", 3, 0.3), ("blaze_rod", 5, 0.8)]},
    ]
    
    def __init__(self, session):
        self.session = session
    
    def enter_nether(self, player):
        if player.level < 10:
            return False, "❌ تحتاج مستوى 10 لدخول النذر!"
        if not player.has_item("eye_of_ender", 1):
            return False, "❌ تحتاج عين إندر لفتح بوابة النذر!"
        player.remove_item("eye_of_ender", 1)
        player.in_nether = True
        self.session.commit()
        return True, "🔥 دخلت النذر! عالم الجحيم الخطير..."
    
    def leave_nether(self, player):
        player.in_nether = False
        self.session.commit()
        return True, "🌍 عدت إلى العالم العادي!"
    
    def explore_nether(self, player):
        events = []
        
        # 35% قتال مع عدو
        if random.random() < 0.35:
            mob = random.choice(self.NETHER_MOBS)
            events.append({
                'type': 'enemy',
                'data': mob,
                'msg': f"⚔️ {mob['emoji']} {mob['name']} يهاجمك فجأة!"
            })
        
        # 25% كنز
        if random.random() < 0.25:
            item = random.choice(list(self.NETHER_ITEMS.values()))
            amt = random.randint(2, 5 + (player.luck or 0) // 5)
            player.add_item(item['name'], amt)
            events.append({
                'type': 'loot',
                'msg': f"🎁 وجدت صندوقاً في الحمم! {item['emoji']} {item['name']} x{amt}!"
            })
        
        # 15% فخ
        if random.random() < 0.15:
            damage = random.randint(5, 15)
            player.current_health = max(0, player.current_health - damage)
            events.append({
                'type': 'damage',
                'msg': f"💥 انفجرت أرض الحمم تحتك! -{damage} صحة"
            })
        
        # 10% بوابة سرية (توصلك لكنز كبير)
        if random.random() < 0.1:
            big_rewards = [
                {"name": "diamond", "emoji": "💎", "amt": random.randint(2, 5)},
                {"name": "netherite_scrap", "emoji": "⚫", "amt": random.randint(3, 5)},
                {"name": "gold_ore", "emoji": "✨", "amt": random.randint(10, 20)},
                {"name": "blaze_rod", "emoji": "🔥", "amt": random.randint(5, 10)},
            ]
            reward = random.choice(big_rewards)
            player.add_item(reward['name'], reward['amt'])
            events.append({
                'type': 'loot',
                'msg': f"🌀 بوابة سرية! وجدت {reward['emoji']} {reward['name']} x{reward['amt']}!"
            })
        
        # 5% زعيم
        if random.random() < 0.05:
            boss = self.NETHER_MOBS[-1]
            events.append({
                'type': 'enemy',
                'data': boss,
                'msg': f"👾 **ظهر بيدرازين - زعيم النذر!**\n⚔️ استعد للمعركة!"
            })
        
        self.session.commit()
        return events
    
    def get_nether_menu(self):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🔍 استكشاف", callback_data="nether_explore"),
            types.InlineKeyboardButton("📦 مخزوني", callback_data="nether_inventory")
        )
        kb.add(
            types.InlineKeyboardButton("❤️ حالتي", callback_data="nether_status"),
            types.InlineKeyboardButton("🏃 خروج", callback_data="nether_leave")
        )
        return kb

# ===============================
# 10. رسم المنزل بمكعبات ماينكرافت
# ===============================

class MinecraftHouseDrawer:
    
    HOUSES = {
        "wooden": {
            "name": "بيت خشبي",
            "emoji": "🏠",
            "blocks": {
                "wall": "🟫",
                "roof": "🟩",
                "door": "🟧",
                "window": "🟦",
                "chimney": "⬛",
                "ground": "🟩",
                "light": "🟨"
            },
            "layout": [
                "  🟩🟩🟩  ",
                " 🟩🟫🟫🟫🟩 ",
                "🟩🟫🟫🟫🟫🟫🟩",
                "🟫🟫🟫🟧🟫🟫🟫",
                "🟫🟫🟦🟫🟦🟫🟫",
                "🟫🟫🟫🟫🟫🟫🟫",
                "🟩🟩🟩🟩🟩🟩🟩"
            ]
        },
        "stone": {
            "name": "بيت حجري",
            "emoji": "🏰",
            "blocks": {
                "wall": "⬜",
                "roof": "⬛",
                "door": "🟧",
                "window": "🟦",
                "chimney": "⬛",
                "ground": "🟩",
                "light": "🟨"
            },
            "layout": [
                "  ⬛⬛⬛  ",
                " ⬛⬜⬜⬜⬛ ",
                "⬛⬜⬜⬜⬜⬜⬛",
                "⬜⬜⬜🟧⬜⬜⬜",
                "⬜⬜🟦⬜🟦⬜⬜",
                "⬜⬜⬜⬜⬜⬜⬜",
                "🟩🟩🟩🟩🟩🟩🟩"
            ]
        },
        "mansion": {
            "name": "قصر فاخر",
            "emoji": "🏛️",
            "blocks": {
                "wall": "🟪",
                "roof": "🟨",
                "door": "🟧",
                "window": "🟦",
                "chimney": "⬛",
                "ground": "🟩",
                "light": "🟨"
            },
            "layout": [
                "  🟨🟨🟨  ",
                " 🟨🟪🟪🟪🟨 ",
                "🟨🟪🟪🟪🟪🟪🟨",
                "🟪🟪🟪🟧🟪🟪🟪",
                "🟪🟪🟦🟪🟦🟪🟪",
                "🟪🟪🟪🟪🟪🟪🟪",
                "🟨🟨🟨🟨🟨🟨🟨"
            ]
        },
        "nether": {
            "name": "بيت نذري",
            "emoji": "🔥",
            "blocks": {
                "wall": "🟥",
                "roof": "🟧",
                "door": "🟪",
                "window": "🟨",
                "chimney": "⬛",
                "ground": "🟥",
                "light": "🟧"
            },
            "layout": [
                "  🟧🟧🟧  ",
                " 🟧🟥🟥🟥🟧 ",
                "🟧🟥🟥🟥🟥🟥🟧",
                "🟥🟥🟥🟪🟥🟥🟥",
                "🟥🟥🟨🟥🟨🟥🟥",
                "🟥🟥🟥🟥🟥🟥🟥",
                "🟥🟥🟥🟥🟥🟥🟥"
            ]
        }
    }
    
    @classmethod
    def draw_house(cls, house_type, show_owner=False, owner_name="", level=1):
        """رسم بيت بمكعبات ماينكرافت"""
        if house_type not in cls.HOUSES:
            return "🏚️ لا يوجد بيت"
        
        house = cls.HOUSES[house_type]
        layout = house["layout"]
        
        result = []
        if show_owner and owner_name:
            result.append(f"🏠 {house['name']} - المستوى {level}")
            result.append("")
        
        result.extend(layout)
        
        result.append("")
        result.append(f"📊 المستوى: {level}")
        result.append(f"👤 المالك: {owner_name if show_owner else 'غير معروف'}")
        
        return "\n".join(result)
    
    @classmethod
    def get_house_art(cls, player):
        """جلب رسم البيت للاعب"""
        # التحقق من وجود بناء قيد التنفيذ
        if player.user_id in building_system.building_progress:
            progress = building_system.building_progress[player.user_id]
            house_type = progress["house_type"]
            stage_index = progress["stage_index"]
            stages = progress["stages"]
            
            progress_percent = int((stage_index / len(stages)) * 100)
            
            if stage_index >= len(stages) - 1:
                return cls.draw_house(house_type, True, player.username, 1)
            else:
                return f"""🏗️ **قيد البناء...** ({progress_percent}%)

🟫🟫🟫🟫🟫🟫🟫
🟫🟫⬜⬜⬜🟫🟫
🟫🟫⬜⬜⬜🟫🟫
🟫🟫⬜⬜⬜🟫🟫
🟫🟫🟫🟫🟫🟫🟫
🟩🟩🟩🟩🟩🟩🟩

⏳ المرحلة: {building_system.BUILDING_STAGES[progress['current_stage']]['name']}"""
        
        # إذا كان البيت مكتمل (من قاعدة البيانات)
        if player.house_type:
            return cls.draw_house(player.house_type, True, player.username, 1)
        
        return "🏚️ لا يوجد بيت"

# ===============================
# 11. البوت (الكامل المُعدل)
# ===============================

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ لم يتم العثور على TOKEN!")
    exit(1)

bot = telebot.TeleBot(TOKEN)
session = Session()
gm = GameMechanics(session)
battle_system = BattleSystem(session)
building_system = BuildingSystem(session)
temple_system = TempleSystem(session)
ender_dragon = EnderDragonSystem(session)
nether = NetherSystem(session)

chop_sessions = {}
mine_sessions = {}
battle_sessions = {}
village_quests = {}
temple_puzzle_answers = {}

# ===== Decorator لإدارة الجلسة بشكل آمن =====
def safe_session(func):
    """Decorator لضمان rollback قبل وبعد تنفيذ الدالة"""
    def wrapper(*args, **kwargs):
        try:
            session.rollback()  # تنظيف أي جلسة معلقة
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            session.rollback()
            print(f"⚠️ Session error in {func.__name__}: {e}")
            # محاولة إرسال رسالة خطأ للمستخدم إذا كان ذلك ممكناً
            try:
                if args and hasattr(args[0], 'chat'):
                    bot.send_message(args[0].chat.id, "⚠️ حدث خطأ في قاعدة البيانات. حاول مرة أخرى.")
            except:
                pass
            raise
    return wrapper

def menu(player=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # إذا كان اللاعب في النذر
    if player and player.in_nether:
        kb.add("🔥 النذر")
        kb.add("🔙 رجوع")
        return kb
    
    # القائمة العادية (مع إضافة زر المساعدة)
    kb.add("🌳 الغابة", "🕳️ الكهف")
    kb.add("🏘️ القرية", "🎒 مخزوني")
    kb.add("🛠️ التصنيع", "🏠 بناء")
    kb.add("🍖 أكل", "🗑️ حذف")
    kb.add("❤️ حالتي", "📊 مهاراتي")
    kb.add("🔥 النذر", "🐉 التنين")
    kb.add("📖 مساعدة", "🔙 رجوع")
    return kb

def edit_msg(bot, chat_id, msg_id, text, reply_markup=None):
    try:
        if reply_markup:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
        else:
            bot.edit_message_text(text, chat_id, msg_id)
        return True
    except Exception as e:
        if "message is not modified" not in str(e) and "message to edit not found" not in str(e):
            bot.send_message(chat_id, text, reply_markup=reply_markup)
        return False

def update_time_and_events(player):
    time_of_day = gm.update_game_time(player)
    events = WorldData.get_random_event(player.is_night())
    if events and events.get('type') == 'loot':
        player.add_item(events['item'], events['amount'])
        session.commit()
    return time_of_day, events

@bot.message_handler(commands=['start'])
@safe_session
def start(msg):
    p, new = get_player(session, msg.from_user.id, msg.from_user.first_name)
    if new:
        txt = "🌟 أهلاً بك في عالم ماينكرافت!\n\nاستخدم الأزرار للتنقل.\n📖 للتعليمات اضغط زر المساعدة"
    else:
        tod = p.get_time_of_day()
        txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu(p))

# ===============================
# 12. زر المساعدة - دليل المستخدم الشامل (بدون Markdown)
# ===============================

@bot.message_handler(func=lambda m: m.text == "📖 مساعدة")
@safe_session
def help_menu(msg):
    """دليل المستخدم الشامل للعبة"""
    p, _ = get_player(session, msg.from_user.id)
    
    help_text = """
📖 دليل ماينكرافت بوت 🎮

━━━━━━━━━━━━━━━━━━━━━━

🌟 البداية
• استخدم الأزرار للتنقل
• ابدأ بجمع الموارد من الغابة والكهف
• كلما زاد مستواك، زادت قدراتك

━━━━━━━━━━━━━━━━━━━━━━

🌳 الغابة
• قطع الأشجار للحصول على الخشب
• صيد الحيوانات للحصول على الطعام والجلود
• استكشاف الغابة قد يظهر لك معابد قديمة

🕳️ الكهف
• تكسير الحجارة للحصول على المعادن
• حجر → فحم → حديد → ذهب → ألماس
• تحتاج معولاً لتكسير الحجارة!

━━━━━━━━━━━━━━━━━━━━━━

🏠 البناء
• المستوى 1: بيت خشبي 🏠
• المستوى 5: بيت حجري 🏰
• المستوى 15: قصر فاخر 🏛️
• كل بيت يمنحك مكافآت دائمة

🛠️ التصنيع
• اصنع الأدوات والأسلحة والدروع
• استخدم الفرن لصهر المعادن
• افتح وصفات جديدة مع تقدم المستوى

━━━━━━━━━━━━━━━━━━━━━━

🔥 النذر
• المستوى 10+ للدخول
• تحتاج عين إندر للبوابة
• أعداء أقوياء ومكافآت نادرة
• خردة النذريت، عصا البلاز، وغيرها

🐉 التنين - قتال جماعي!
• المستوى 20+ للمشاركة
• تحتاج سيفاً ألماسياً أو قوساً
• 4 أبراج بلورات يجب كسرها
• استخدم السيف للهجوم والقوس للأبراج
• معركة بثلاث مراحل!
• انضم للمعركة مع لاعبين آخرين!

━━━━━━━━━━━━━━━━━━━━━━

🏘️ القرية
• نوم لتجديد الصحة والجوع
• مهام يومية للحصول على مكافآت
• متجر لشراء الموارد
• تبادل مع القرويين

━━━━━━━━━━━━━━━━━━━━━━

⚔️ القتال
• استخدم /equip لتجهيز السلاح
• السيوف: خشبي → حجري → حديدي → ألماسي
• الدروع تحمي من الهجمات
• في الليل، الأعداء أقوى!

━━━━━━━━━━━━━━━━━━━━━━

📊 المهارات
• كل 5 مستويات تحصل على نقطة مهارة
• القوة تزيد الضرر
• السرعة تساعد في الهروب
• التحمل يزيد الصحة
• الحظ يزيد فرص السقوط النادر

━━━━━━━━━━━━━━━━━━━━━━

💡 نصائح مهمة
• حافظ على جوعك عالياً 🍖
• نام في القرية لتجديد صحتك
• استخدم الأدوات المناسبة لكل مهمة
• خزن الموارد النادرة للتصنيع المتقدم
• شارك في المعابد للحصول على كنوز

━━━━━━━━━━━━━━━━━━━━━━

🔧 الأوامر السريعة
/equip اسم_الأداة - تجهيز أداة
/additem اسم_العنصر العدد - إضافة عنصر (للمطور)
/buy اسم_العنصر - شراء من المتجر
/trade رقم - مبادلة مع القروي

🐉 أوامر التنين:
/dragon_attack - هجوم بالسيف
/dragon_shot - إطلاق سهم
/dragon_crystal [1-4] - كسر برج
/dragon_heal - جرعة شفاء
/dragon_join - الانضمام للمعركة
/dragon_status - حالة المعركة

━━━━━━━━━━━━━━━━━━━━━━

📱 طور اللعبة معنا!
اقتراحاتك مرحب بها لتحسين اللعبة 🚀
"""
    
    # إضافة زر العودة مع الحالة الحالية
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔙 العودة للقائمة", callback_data="back_to_menu"))
    
    bot.send_message(msg.chat.id, help_text, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "back_to_menu")
@safe_session
def back_to_menu(call):
    """العودة للقائمة الرئيسية من المساعدة"""
    p, _ = get_player(session, call.from_user.id)
    tod = p.get_time_of_day()
    txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, menu(p))

# ===============================
# 13. أوامر التنين المتطورة
# ===============================

@bot.message_handler(commands=['dragon_attack'])
@safe_session
def dragon_attack_cmd(msg):
    """هجوم بالسيف على التنين"""
    p, _ = get_player(session, msg.from_user.id)
    
    if not ender_dragon.dragon_active:
        return bot.send_message(msg.chat.id, "❌ لا يوجد تنين نشط!")
    
    if p.user_id not in ender_dragon.fighters:
        return bot.send_message(msg.chat.id, "❌ لست في المعركة! استخدم /dragon_join")
    
    success, response = ender_dragon.player_attack_sword(p)
    if not success:
        return bot.send_message(msg.chat.id, response)
    
    status = ender_dragon.get_fight_status(p)
    bot.send_message(msg.chat.id, f"{response}\n\n{status}")

@bot.message_handler(commands=['dragon_shot'])
@safe_session
def dragon_shot_cmd(msg):
    """إطلاق سهم - لكسر الأبراج أو إيذاء التنين"""
    p, _ = get_player(session, msg.from_user.id)
    
    if not ender_dragon.dragon_active:
        return bot.send_message(msg.chat.id, "❌ لا يوجد تنين نشط!")
    
    if p.user_id not in ender_dragon.fighters:
        return bot.send_message(msg.chat.id, "❌ لست في المعركة! استخدم /dragon_join")
    
    success, response = ender_dragon.player_shoot_bow(p)
    if not success:
        return bot.send_message(msg.chat.id, response)
    
    status = ender_dragon.get_fight_status(p)
    bot.send_message(msg.chat.id, f"{response}\n\n{status}")

@bot.message_handler(commands=['dragon_crystal'])
@safe_session
def dragon_crystal_cmd(msg):
    """كسر برج معين"""
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    
    if len(args) < 2:
        return bot.send_message(msg.chat.id, "❌ استخدم: /dragon_crystal [رقم البرج 1-4]")
    
    try:
        crystal_id = int(args[1])
    except:
        return bot.send_message(msg.chat.id, "❌ رقم غير صحيح!")
    
    if not ender_dragon.dragon_active:
        return bot.send_message(msg.chat.id, "❌ لا يوجد تنين نشط!")
    
    if p.user_id not in ender_dragon.fighters:
        return bot.send_message(msg.chat.id, "❌ لست في المعركة! استخدم /dragon_join")
    
    success, response = ender_dragon.destroy_crystal(p, crystal_id)
    if not success:
        return bot.send_message(msg.chat.id, response)
    
    status = ender_dragon.get_fight_status(p)
    bot.send_message(msg.chat.id, f"{response}\n\n{status}")

@bot.message_handler(commands=['dragon_heal'])
@safe_session
def dragon_heal_cmd(msg):
    """استخدام جرعة شفاء"""
    p, _ = get_player(session, msg.from_user.id)
    
    if not ender_dragon.dragon_active:
        return bot.send_message(msg.chat.id, "❌ لا يوجد تنين نشط!")
    
    if p.user_id not in ender_dragon.fighters:
        return bot.send_message(msg.chat.id, "❌ لست في المعركة! استخدم /dragon_join")
    
    success, response = ender_dragon.player_heal(p)
    if not success:
        return bot.send_message(msg.chat.id, response)
    
    status = ender_dragon.get_fight_status(p)
    bot.send_message(msg.chat.id, f"{response}\n\n{status}")

@bot.message_handler(commands=['dragon_join'])
@safe_session
def dragon_join_cmd(msg):
    """الانضمام للمعركة الجماعية"""
    p, _ = get_player(session, msg.from_user.id)
    
    success, response = ender_dragon.join_fight(p)
    if success:
        status = ender_dragon.get_fight_status(p)
        bot.send_message(msg.chat.id, f"{response}\n\n{status}")
    else:
        bot.send_message(msg.chat.id, response)

@bot.message_handler(commands=['dragon_status'])
@safe_session
def dragon_status_cmd(msg):
    """عرض حالة المعركة الحالية"""
    p, _ = get_player(session, msg.from_user.id)
    status = ender_dragon.get_fight_status(p)
    bot.send_message(msg.chat.id, status)

# ===============================
# 14. باقي أوامر البوت
# ===============================

@bot.message_handler(commands=['additem'])
@safe_session
def add_item_cmd(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 3:
        return bot.send_message(msg.chat.id, "استخدم: /additem اسم_العنصر العدد")
    try:
        amt = int(args[2])
    except:
        return bot.send_message(msg.chat.id, "❌ العدد يجب أن يكون رقماً")
    
    valid_items = [
        "oak_wood", "spruce_wood", "birch_wood", "jungle_wood",
        "stone", "coal", "iron_ore", "gold_ore", "diamond", "emerald",
        "apple", "bread", "cooked_beef", "honey", "golden_apple",
        "raw_beef", "tropical_fruit", "cooked_chicken", "cooked_pork", "cooked_mutton",
        "leather", "feather", "bone", "wool", "milk", "egg",
        "wooden_planks", "sticks", "crafting_table", "furnace",
        "wooden_sword", "stone_sword", "iron_sword", "diamond_sword",
        "bow", "arrow",
        "wooden_axe", "stone_axe", "iron_axe", "diamond_axe",
        "stone_pickaxe", "iron_pickaxe", "diamond_pickaxe",
        "wooden_helmet", "stone_helmet", "iron_helmet", "diamond_helmet",
        "wooden_chestplate", "stone_chestplate", "iron_chestplate", "diamond_chestplate",
        "wooden_leggings", "stone_leggings", "iron_leggings", "diamond_leggings",
        "wooden_boots", "stone_boots", "iron_boots", "diamond_boots",
        "fire_chestplate", "elytra",
        "eye_of_ender", "ender_pearl", "blaze_rod",
        "nether_wart", "ghast_tear", "magma_cream", "netherite_scrap",
        "soul_sand", "nether_brick", "fiery_coal",
        "healing_potion", "enchanted_book",
        "wheat", "sap", "mushroom", "spider_silk", "spider_eye",
        "gunpowder", "rotten_flesh", "torch", "glass", "fence", "wooden_door",
        "bear_meat", "bear_pelt", "saddle", "hoof"
    ]
    
    if args[1] not in valid_items:
        return bot.send_message(msg.chat.id, f"❌ {args[1]} غير معروف!")
    
    p.add_item(args[1], amt)
    session.commit()
    bot.send_message(msg.chat.id, f"✅ تم إضافة {amt} من {args[1]}!")

@bot.message_handler(commands=['equip'])
@safe_session
def equip_item(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 2:
        return bot.send_message(msg.chat.id, "❌ استخدم: /equip اسم_الأداة\nمثال: /equip iron_sword")
    
    item_name = args[1]
    weapons = ["wooden_sword", "stone_sword", "iron_sword", "diamond_sword", "bow"]
    axes = ["wooden_axe", "stone_axe", "iron_axe", "diamond_axe"]
    pickaxes = ["stone_pickaxe", "iron_pickaxe", "diamond_pickaxe"]
    helmets = ["wooden_helmet", "stone_helmet", "iron_helmet", "diamond_helmet"]
    chestplates = ["wooden_chestplate", "stone_chestplate", "iron_chestplate", "diamond_chestplate", "fire_chestplate"]
    leggings = ["wooden_leggings", "stone_leggings", "iron_leggings", "diamond_leggings"]
    boots = ["wooden_boots", "stone_boots", "iron_boots", "diamond_boots"]
    all_tools = weapons + axes + pickaxes + helmets + chestplates + leggings + boots
    
    if item_name not in all_tools:
        return bot.send_message(msg.chat.id, f"❌ {item_name} غير معروف")
    if not p.has_item(item_name, 1):
        return bot.send_message(msg.chat.id, f"❌ ليس لديك {item_name}!\nاستخدم /additem {item_name} 1")
    
    eq = p.get_equip()
    if item_name in weapons or item_name in axes or item_name in pickaxes:
        old = eq.get("weapon")
        eq["weapon"] = item_name
        p.remove_item(item_name, 1)
        if old:
            p.add_item(old, 1)
    elif item_name in helmets:
        old = eq.get("helmet")
        eq["helmet"] = item_name
        p.remove_item(item_name, 1)
        if old:
            p.add_item(old, 1)
    elif item_name in chestplates:
        old = eq.get("chestplate")
        eq["chestplate"] = item_name
        p.remove_item(item_name, 1)
        if old:
            p.add_item(old, 1)
    elif item_name in leggings:
        old = eq.get("leggings")
        eq["leggings"] = item_name
        p.remove_item(item_name, 1)
        if old:
            p.add_item(old, 1)
    elif item_name in boots:
        old = eq.get("boots")
        eq["boots"] = item_name
        p.remove_item(item_name, 1)
        if old:
            p.add_item(old, 1)
    
    p.save_equip(eq)
    session.commit()
    
    session.refresh(p)
    eq2 = p.get_equip()
    damage = gm.calc_damage(p)
    defense = gm.calc_defense(p)
    
    txt = f"✅ تم تجهيز {item_name}!\n\n🛡️ **التجهيزات الحالية:**\n"
    txt += f"⚔️ السلاح/الأداة: {eq2.get('weapon') or 'لا يوجد'}\n"
    txt += f"🪖 الخوذة: {eq2.get('helmet') or 'لا يوجد'}\n"
    txt += f"👕 الصدرية: {eq2.get('chestplate') or 'لا يوجد'}\n"
    txt += f"👖 البنطلون: {eq2.get('leggings') or 'لا يوجد'}\n"
    txt += f"👢 الحذاء: {eq2.get('boots') or 'لا يوجد'}\n"
    txt += f"\n📊 **الإحصائيات:**\n🗡️ الضرر: {damage}\n🛡️ الدفاع: {defense}"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text in ["🌳 الغابة", "🕳️ الكهف"])
@safe_session
def area_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    
    if p.in_nether:
        return bot.send_message(msg.chat.id, "❌ لا يمكنك الذهاب للغابة أو الكهف وأنت في النذر!")
    
    is_forest = msg.text == "🌳 الغابة"
    time_of_day, events = update_time_and_events(p)
    is_night = p.is_night()
    
    txt = f"{'🌳 الغابة' if is_forest else '🕳️ الكهف'} | 🕐 {time_of_day}\n\n"
    if events:
        txt += f"✅ {events['msg']}\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    if is_forest:
        trees = WorldData.get_trees()
        for tree in random.sample(trees, min(2, len(trees))):
            break_time = gm.get_break_time(p, tree['break_time'])
            txt += f"🌳 {tree['name']} ({tree['blocks']} مكعبات) ⏱️{break_time:.1f}ث\n"
            kb.add(types.InlineKeyboardButton(f"🪓 {tree['name']}", callback_data=f"chop_{tree['name']}"))
        if not is_night:
            animals = list(WorldData.get_animals().keys())
            for animal in random.sample(animals, min(2, len(animals))):
                kb.add(types.InlineKeyboardButton(f"🏹 {animal}", callback_data=f"hunt_{animal}"))
        if random.random() < 0.15 and not is_night:
            kb.add(types.InlineKeyboardButton("🏛️ معبد قديم!", callback_data="temple_enter"))
    else:
        rocks = WorldData.get_rocks()
        for rock in random.sample(rocks, min(2, len(rocks))):
            break_time = gm.get_break_time(p, rock['break_time'])
            txt += f"🪨 {rock['name']} ({rock['blocks']} مكعبات) ⏱️{break_time:.1f}ث\n"
            kb.add(types.InlineKeyboardButton(f"⛏️ {rock['name']}", callback_data=f"mine_{rock['name']}"))
    
    kb.add(types.InlineKeyboardButton("🔍 استكشاف", callback_data=f"explore_{'forest' if is_forest else 'cave'}"))
    if is_night:
        txt += "\n🌙 الليل! الأعداء في كل مكان!"
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🏘️ القرية")
@safe_session
def village(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_events(p)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("😴 نوم", callback_data="v_sleep"), types.InlineKeyboardButton("📋 مهام", callback_data="v_quests"))
    kb.add(types.InlineKeyboardButton("🛒 متجر", callback_data="v_shop"), types.InlineKeyboardButton("🏅 تبادل", callback_data="v_trade"))
    kb.add(types.InlineKeyboardButton("⚔️ بطل القرية", callback_data="v_champion"))
    bot.send_message(msg.chat.id, f"🏘️ القرية\n🕐 {p.get_time_of_day()}\n📊 مستوى القرية: {p.level//2 + 1}", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🛠️ التصنيع")
@safe_session
def craft_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    recipes = CraftingSystem.get_recipes(p)
    kb = types.InlineKeyboardMarkup(row_width=1)
    txt = f"🛠️ **التصنيع**\n🕐 {p.get_time_of_day()}\n\n"
    if recipes:
        for i, r in enumerate(recipes[:15]):
            materials = ", ".join([f"{k}×{v}" for k, v in r['in'].items()])
            kb.add(types.InlineKeyboardButton(f"{r['emoji']} {r['name']} ({materials})", callback_data=f"craft_{i}"))
    else:
        txt += "📭 لا توجد وصفات متاحة\n\n"
    if p.has_item("furnace"):
        kb.add(types.InlineKeyboardButton("🔥 استخدام الفرن", callback_data="furnace_menu"))
        txt += "\n🔥 لديك فرن! استخدمه لصهر المعادن."
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🏠 بناء")
@safe_session
def building_menu(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_events(p)
    
    status = building_system.get_building_status(p)
    if status:
        if status["is_complete"]:
            success, msg_text = building_system.complete_stage(p)
            if success:
                p.house_type = status["house_type"]
                session.commit()
                bot.send_message(msg.chat.id, msg_text)
                building_menu(msg)
                return
            else:
                bot.send_message(msg.chat.id, msg_text)
                return
        else:
            progress_bar = '█' * (status['progress']//10) + '░' * (10 - status['progress']//10)
            txt = f"🏗️ جارٍ البناء...\n"
            txt += f"🏠 البيت: {status['house_name']}\n"
            txt += f"📌 المرحلة: {status['stage_name']}\n"
            txt += f"📊 التقدم: {progress_bar} {status['progress']}%\n"
            txt += f"⏳ الوقت المتبقي: {status['time_left_str']}\n"
            
            if status['progress'] < 30:
                txt += "🔄 بداية العمل..."
            elif status['progress'] < 60:
                txt += "⚒️ جارٍ البناء..."
            elif status['progress'] < 90:
                txt += "🔨 يقترب من الانتهاء..."
            else:
                txt += "🎉 يكاد ينجز!"
            
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="build_status"))
            kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="build_cancel"))
            bot.send_message(msg.chat.id, txt, reply_markup=kb)
            return
    
    available = building_system.get_available_houses(p)
    if not available:
        return bot.send_message(msg.chat.id, "❌ ليس لديك مستوى كافٍ لبناء أي بيت\n\nالمستويات المطلوبة:\n🏠 خشبي: مستوى 1\n🏰 حجري: مستوى 5\n🏛️ قصر: مستوى 15")
    
    txt = "🏠 اختر نوع البيت الذي تريد بنائه:\n\n"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for house_type in available:
        house = building_system.HOUSE_TYPES[house_type]
        stages_info = building_system.get_building_stages_info(house_type)
        total_resources = {}
        for stage in stages_info:
            for item, amt in stage["resources"].items():
                total_resources[item] = total_resources.get(item, 0) + amt
        resources_text = ", ".join([f"{k} x{v}" for k, v in total_resources.items()])
        txt += f"{house['emoji']} {house['name']}\n📦 الموارد: {resources_text}\n⭐ المكافآت: {house['bonus']}\n\n"
        kb.add(types.InlineKeyboardButton(f"{house['emoji']} بناء {house['name']}", callback_data=f"build_{house_type}"))
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🍖 أكل")
@safe_session
def eat_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    foods = [s for s in inv.values() if s and s['name'] in ["apple", "bread", "cooked_beef", "honey", "golden_apple", "raw_beef", "tropical_fruit", "cooked_chicken", "cooked_pork", "cooked_mutton"]]
    if not foods:
        return bot.send_message(msg.chat.id, "🍖 لا طعام")
    kb = types.InlineKeyboardMarkup(row_width=2)
    for f in foods[:10]:
        kb.add(types.InlineKeyboardButton(f"{f['name']} x{f['amount']}", callback_data=f"eat_{f['name']}"))
    bot.send_message(msg.chat.id, "🍖 اختر الطعام", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🗑️ حذف")
@safe_session
def delete_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.send_message(msg.chat.id, "📭 المخزون فارغ")
    
    txt = "🗑️ اختر عنصراً للحذف:\n\n"
    kb = types.InlineKeyboardMarkup(row_width=3)
    for idx, slot in items:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
        kb.add(types.InlineKeyboardButton(f"{idx+1}", callback_data=f"del_{idx}"))
    
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "❤️ حالتي")
@safe_session
def status(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    titles = p.titles if isinstance(p.titles, list) else []
    eq = p.get_equip()
    damage = gm.calc_damage(p)
    defense = gm.calc_defense(p)
    
    house_art = MinecraftHouseDrawer.get_house_art(p)
    
    txt = f"👤 {p.username} | ⭐ Lv.{p.level}\n"
    txt += f"❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n"
    txt += f"🗡️ ضرر: {damage} | 🛡️ دفاع: {defense}\n"
    txt += f"🕐 {p.get_time_of_day()}\n"
    txt += f"⚔️ السلاح/الأداة: {eq.get('weapon', 'لا يوجد')}\n"
    txt += f"🪖 الخوذة: {eq.get('helmet', 'لا يوجد')}\n"
    txt += f"👕 الصدرية: {eq.get('chestplate', 'لا يوجد')}\n"
    txt += f"👖 البنطلون: {eq.get('leggings', 'لا يوجد')}\n"
    txt += f"👢 الحذاء: {eq.get('boots', 'لا يوجد')}\n"
    txt += f"\n🏠 **منزلك:**\n{house_art}\n"
    txt += f"🏅 {', '.join(titles) if titles else 'لا ألقاب'}\n"
    txt += f"🐺 حيوان: {p.pet or 'لا يوجد'}\n"
    txt += f"🏛️ معابد: {p.temples_visited or 0}\n"
    txt += f"🐉 التنين: {'✅ هزمته' if p.defeated_ender_dragon else '❌ لم يهزم'}"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "🔥 النذر")
@safe_session
def nether_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    
    if p.in_nether:
        kb = nether.get_nether_menu()
        txt = f"🔥 **أنت في النذر!**\n\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n📊 المستوى: {p.level}"
        bot.send_message(msg.chat.id, txt, reply_markup=kb)
        return
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🚪 دخول النذر", callback_data="nether_enter"),
        types.InlineKeyboardButton("ℹ️ معلومات", callback_data="nether_info")
    )
    bot.send_message(msg.chat.id, "🔥 **النذر - عالم الجحيم**\n\n⚠️ منطقة خطيرة جداً!\n📍 المستوى المطلوب: 10\n💀 أعداء أقوياء ومكافآت نادرة", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🐉 التنين")
@safe_session
def dragon_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    status = ender_dragon.get_fight_status(p)
    can, msg_text = ender_dragon.can_fight_dragon(p)
    kb = types.InlineKeyboardMarkup(row_width=1)
    if can:
        kb.add(types.InlineKeyboardButton("🐉 قتال التنين!", callback_data="dragon_fight"))
    kb.add(types.InlineKeyboardButton("📊 حالة التنين", callback_data="dragon_status"))
    kb.add(types.InlineKeyboardButton("👥 انضم للمعركة", callback_data="dragon_join_party"))
    bot.send_message(msg.chat.id, f"{status}\n\n{msg_text}", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📊 مهاراتي")
@safe_session
def skills(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    txt = f"⚔️ قوة: {p.strength} | 💨 سرعة: {p.speed}\n💪 تحمل: {p.endurance} | 🍀 حظ: {p.luck}\n🎯 نقاط: {p.skill_points}"
    if p.skill_points > 0:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("⚔️ قوة", callback_data="sk_strength"), types.InlineKeyboardButton("💨 سرعة", callback_data="sk_speed"))
        kb.add(types.InlineKeyboardButton("💪 تحمل", callback_data="sk_endurance"), types.InlineKeyboardButton("🍀 حظ", callback_data="sk_luck"))
        bot.send_message(msg.chat.id, txt, reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "🎒 مخزوني")
@safe_session
def inventory(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.send_message(msg.chat.id, f"📭 المخزون فارغ\n🕐 {p.get_time_of_day()}")
    
    txt = f"🎒 **مخزونك**\n🕐 {p.get_time_of_day()}\n📦 {len(items)} عنصر\n\n"
    
    for idx, slot in items:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "🔙 رجوع")
@safe_session
def go_back(msg):
    p, _ = get_player(session, msg.from_user.id)
    
    if p.in_nether:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ نعم، اخرج", callback_data="nether_leave"),
            types.InlineKeyboardButton("❌ لا، ابق", callback_data="nether_stay")
        )
        bot.send_message(msg.chat.id, "🔥 أنت في النذر! هل تريد العودة إلى العالم العادي؟", reply_markup=kb)
        return
    
    tod = p.get_time_of_day()
    txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu(p))

# ===============================
# 15. جميع Callbacks - مكتوبة كاملة
# ===============================

# Callbacks للغابة والكهف
@bot.callback_query_handler(func=lambda c: c.data.startswith("chop_"))
@safe_session
def start_chop(call):
    session.rollback()
    tree_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 لا يمكنك قطع الأشجار في الليل!")
    trees = WorldData.get_trees()
    tree = next((t for t in trees if t['name'] == tree_name), None)
    if not tree:
        return bot.answer_callback_query(call.id, "❌ شجرة غير موجودة")
    break_time = gm.get_break_time(p, tree['break_time'])
    chop_sessions[call.from_user.id] = {"tree": tree, "blocks": tree['blocks'], "break_time": break_time}
    animation = gm.get_tree_animation(tree['blocks'], tree['blocks'])
    txt = f"🪓 {tree['name']}\nمتبقي: {tree['blocks']} مكعبات\n{animation}\n\n⏳ وقت التكسير: {break_time:.1f} ثانية لكل مكعب\n\nاضغط اكسر!"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_chop")
@safe_session
def do_chop(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in chop_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    data = chop_sessions[call.from_user.id]
    tree = data["tree"]
    break_time = data.get("break_time", 2)
    bot.answer_callback_query(call.id, f"⏳ جارٍ التكسير... {break_time:.1f} ثانية", show_alert=True)
    time.sleep(break_time)
    data["blocks"] -= 1
    result = gm.chop_block(p, tree)
    session.commit()
    animation = gm.get_tree_animation(tree['blocks'], data["blocks"])
    if data["blocks"] <= 0:
        txt = f"✅ انكسرت {tree['name']}!\n{animation}\n\n🎁 {', '.join(result['rewards'])}\n⭐ +{result['xp']}XP"
        del chop_sessions[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
    else:
        txt = f"🪓 {tree['name']}\nمتبقي: {data['blocks']} مكعبات\n{animation}\n\n🎁 {', '.join(result['rewards'])}\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20\n⭐ +{result['xp']}XP"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("mine_"))
@safe_session
def start_mine(call):
    session.rollback()
    rock_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    eq = p.get_equip()
    weapon = eq.get("weapon")
    if not gm.is_valid_pickaxe(weapon):
        return bot.answer_callback_query(call.id, "❌ تحتاج معولاً لتكسير الحجر!\nاستخدم /equip stone_pickaxe")
    rocks = WorldData.get_rocks()
    rock = next((r for r in rocks if r['name'] == rock_name), None)
    if not rock:
        return bot.answer_callback_query(call.id, "❌ حجر غير موجود")
    break_time = gm.get_break_time(p, rock['break_time'])
    mine_sessions[call.from_user.id] = {"rock": rock, "blocks": rock['blocks'], "break_time": break_time}
    animation = gm.get_rock_animation(rock['blocks'], rock['blocks'])
    txt = f"⛏️ {rock['name']}\nمتبقي: {rock['blocks']} مكعبات\n{animation}\n\n⏳ وقت التكسير: {break_time:.1f} ثانية لكل مكعب\n\nاضغط اكسر!"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_mine")
@safe_session
def do_mine(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in mine_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    data = mine_sessions[call.from_user.id]
    rock = data["rock"]
    break_time = data.get("break_time", 3)
    bot.answer_callback_query(call.id, f"⏳ جارٍ التكسير... {break_time:.1f} ثانية", show_alert=True)
    time.sleep(break_time)
    data["blocks"] -= 1
    result = gm.mine_block(p, rock)
    session.commit()
    if result.get("failed"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "❌ فشل التكسير!")
        del mine_sessions[call.from_user.id]
        return
    animation = gm.get_rock_animation(rock['blocks'], data["blocks"])
    if data["blocks"] <= 0:
        txt = f"✅ انكسر {rock['name']}!\n{animation}\n\n🎁 {', '.join(result['rewards'])}\n⭐ +{result['xp']}XP"
        del mine_sessions[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
    else:
        txt = f"⛏️ {rock['name']}\nمتبقي: {data['blocks']} مكعبات\n{animation}\n\n🎁 {', '.join(result['rewards'])}\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20\n⭐ +{result['xp']}XP"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("hunt_"))
@safe_session
def hunt(call):
    session.rollback()
    animal_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 الحيوانات نائمة في الليل!")
    eq = p.get_equip()
    weapon = eq.get("weapon")
    if not weapon or not gm.is_combat_weapon(weapon):
        return bot.answer_callback_query(call.id, "❌ تحتاج سيفاً أو قوساً للصيد!\nاستخدم /equip iron_sword")
    result = gm.hunt_animal(p, animal_name)
    session.commit()
    if "error" in result:
        return bot.answer_callback_query(call.id, result["error"])
    txt = f"🏹 صيد {animal_name}!\n\n🎁 {', '.join(result['rewards'])}"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "temple_enter")
@safe_session
def enter_temple(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    result = temple_system.enter_temple(p)
    if result[0] == False:
        return bot.answer_callback_query(call.id, result[1])
    if result[0] == "puzzle":
        puzzle = result[1]
        txt = f"🏛️ معبد غامض!\n\n📜 **{puzzle['q']}**\n\nاختر الإجابة:"
        answers = list(set([puzzle['a'], "الضوء", "الماء", "الرياح", "التراب", "السماء"]))
        random.shuffle(answers)
        answers = answers[:4]
        kb = types.InlineKeyboardMarkup(row_width=2)
        for ans in answers:
            kb.add(types.InlineKeyboardButton(f"📝 {ans}", callback_data=f"temple_answer_{ans}"))
        temple_puzzle_answers[call.from_user.id] = puzzle
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    elif result[0] == "monster":
        monster = result[1]
        battle_data = battle_system.start_battle(p, monster)
        battle_sessions[call.from_user.id] = battle_data
        txt = f"🏛️ في المعبد!\n\n{monster['emoji']} {monster['name']} يهاجمك!\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n❤️ {monster['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"), types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend"))
        kb.add(types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    elif result[0] == "treasure":
        msg = temple_system.get_temple_reward(p, result[1])
        kb = temple_system.get_temple_menu()
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"🏛️ في المعبد!\n\n{msg}", kb)

@bot.callback_query_handler(func=lambda c: c.data == "temple_explore")
@safe_session
def temple_explore(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    result = temple_system.enter_temple(p)
    if result[0] == False:
        return bot.answer_callback_query(call.id, result[1])
    if result[0] == "puzzle":
        puzzle = result[1]
        txt = f"🏛️ معبد غامض!\n\n📜 **{puzzle['q']}**\n\nاختر الإجابة:"
        answers = list(set([puzzle['a'], "الضوء", "الماء", "الرياح", "التراب", "السماء"]))
        random.shuffle(answers)
        answers = answers[:4]
        kb = types.InlineKeyboardMarkup(row_width=2)
        for ans in answers:
            kb.add(types.InlineKeyboardButton(f"📝 {ans}", callback_data=f"temple_answer_{ans}"))
        temple_puzzle_answers[call.from_user.id] = puzzle
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    elif result[0] == "monster":
        monster = result[1]
        battle_data = battle_system.start_battle(p, monster)
        battle_sessions[call.from_user.id] = battle_data
        txt = f"🏛️ في المعبد!\n\n{monster['emoji']} {monster['name']} يهاجمك!\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n❤️ {monster['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"), types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend"))
        kb.add(types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    elif result[0] == "treasure":
        msg = temple_system.get_temple_reward(p, result[1])
        kb = temple_system.get_temple_menu()
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"🏛️ في المعبد!\n\n{msg}", kb)

@bot.callback_query_handler(func=lambda c: c.data == "temple_leave")
@safe_session
def temple_leave(call):
    session.rollback()
    edit_msg(bot, call.message.chat.id, call.message.message_id, "🚪 خرجت من المعبد")

@bot.callback_query_handler(func=lambda c: c.data.startswith("temple_answer_"))
@safe_session
def temple_answer(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in temple_puzzle_answers:
        return bot.answer_callback_query(call.id, "❌ انتهت جلسة المعبد")
    puzzle = temple_puzzle_answers[call.from_user.id]
    success, msg = temple_system.solve_puzzle(p, puzzle, call.data[14:])
    session.commit()
    del temple_puzzle_answers[call.from_user.id]
    bot.answer_callback_query(call.id, msg)
    kb = temple_system.get_temple_menu()
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"🏛️ **نتيجة اللغز**\n\n{msg}", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_"))
@safe_session
def explore(call):
    session.rollback()
    area = call.data.split("_")[1]
    p, _ = get_player(session, call.from_user.id)
    time_of_day, events = update_time_and_events(p)
    is_night = p.is_night()
    
    if random.random() < 0.2:
        enemies = WorldData.get_enemies(is_night)
        if enemies:
            enemy = random.choice(enemies)
            battle_data = battle_system.start_battle(p, enemy)
            battle_sessions[call.from_user.id] = battle_data
            txt = f"⚔️ هجوم!\n{enemy['emoji']} {enemy['name']} ظهر فجأة!\n🕐 {time_of_day}\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n❤️ {enemy['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"), types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend"))
            kb.add(types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run"))
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
            return
    
    if area == "forest" and random.random() < 0.1 and not is_night:
        txt = f"🏛️ وجدت معبداً قديماً في الغابة!\n🕐 {time_of_day}\n\nهل تريد الدخول؟"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🏛️ دخول المعبد", callback_data="temple_enter"))
        kb.add(types.InlineKeyboardButton("🚶 تخطي", callback_data="skip_temple"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
        return
    
    possible = ["apple", "bread", "coal", "stone", "oak_wood", "feather", "mushroom", "wheat"]
    if is_night:
        possible = ["coal", "iron_ore", "rotten_flesh", "bone", "gunpowder"]
    item = random.choice(possible)
    amt = random.randint(1, 2 + (p.luck or 0) // 10)
    if is_night:
        amt += 1
    p.add_item(item, amt)
    p.add_xp(4 if is_night else 2)
    session.commit()
    txt = f"🔍 استكشاف...\n🕐 {time_of_day}\n\n🎁 وجدت {item} x{amt}!\n⭐ +{4 if is_night else 2}XP"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "skip_temple")
@safe_session
def skip_temple(call):
    session.rollback()
    edit_msg(bot, call.message.chat.id, call.message.message_id, "🚶 واصلت طريقك...")

# Callbacks للقتال
@bot.callback_query_handler(func=lambda c: c.data.startswith("battle_"))
@safe_session
def battle_action(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in battle_sessions:
        return bot.answer_callback_query(call.id, "انتهى القتال")
    battle_data = battle_sessions[call.from_user.id]
    action = call.data[7:]
    time_of_day = gm.update_game_time(p)
    battle_data['is_night'] = p.is_night()
    
    if action == 'attack':
        battle_data = battle_system.player_attack(p, battle_data)
    elif action == 'defend':
        battle_data = battle_system.player_defend(p, battle_data)
    elif action == 'run':
        success, battle_data = battle_system.try_escape(p, battle_data)
        if success:
            del battle_sessions[call.from_user.id]
            session.commit()
            edit_msg(bot, call.message.chat.id, call.message.message_id, f"🏃 هربت!\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-3:]))
            return
    
    if battle_data['enemy_hp'] > 0 and battle_data['player_hp'] > 0:
        battle_data = battle_system.enemy_turn(p, battle_data)
    session.commit()
    status, battle_data = battle_system.check_win(p, battle_data)
    session.commit()
    
    if status == 'win':
        del battle_sessions[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, "🎉 انتصرت!\n\n" + "\n".join(battle_data['log'][-5:]))
        return
    if status == 'dead':
        del battle_sessions[call.from_user.id]
        gm.respawn(p)
        session.commit()
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت!\n\n" + "\n".join(battle_data['log'][-3:]) + "\n\n🔄 تم إحياؤك في الغابة")
        return
    
    battle_data['round'] += 1
    battle_sessions[call.from_user.id] = battle_data
    enemy = battle_data['enemy']
    txt = f"⚔️ الجولة {battle_data['round']}\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-3:])
    txt += f"\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n❤️ {enemy['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"), types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend"))
    kb.add(types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

# Callbacks للتصنيع
@bot.callback_query_handler(func=lambda c: c.data == "furnace_menu")
@safe_session
def furnace_menu(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if not p.has_item("furnace"):
        return bot.answer_callback_query(call.id, "❌ ليس لديك فرن!")
    txt = "🔥 **الفرن**\n\nاختر ما تريد صهره:\n"
    kb = types.InlineKeyboardMarkup(row_width=2)
    has_items = False
    for item, recipe in CraftingSystem.FURNACE_RECIPES.items():
        if p.has_item(item):
            has_items = True
            kb.add(types.InlineKeyboardButton(f"🔄 {item} ← {recipe['out']}", callback_data=f"furnace_{item}"))
    if not has_items:
        txt += "\n📭 ليس لديك مواد قابلة للصهر"
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_craft"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("furnace_"))
@safe_session
def furnace_smelt_callback(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    success, msg = CraftingSystem.furnace_smelt(p, call.data[8:])
    session.commit()
    bot.answer_callback_query(call.id, msg)
    furnace_menu(call)

@bot.callback_query_handler(func=lambda c: c.data == "back_to_craft")
@safe_session
def back_to_craft(call):
    session.rollback()
    craft_menu(call.message)

@bot.callback_query_handler(func=lambda c: c.data.startswith("craft_"))
@safe_session
def do_craft(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    idx = int(call.data.split("_")[1])
    recipes = CraftingSystem.get_recipes(p)
    if idx < len(recipes):
        ok, msg = CraftingSystem.craft(p, recipes[idx])
        session.commit()
        bot.answer_callback_query(call.id, msg)

# Callbacks للبناء
@bot.callback_query_handler(func=lambda c: c.data.startswith("build_"))
@safe_session
def start_build(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    success, msg = building_system.start_building(p, call.data[6:])
    session.commit()
    if success:
        status = building_system.get_building_status(p)
        progress_bar = '█' * 0 + '░' * 10
        txt = f"{msg}\n\n📊 التقدم: {progress_bar} 0%\n⏳ انتظر {status['time_left']} ثانية"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="build_status"))
        kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="build_cancel"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "build_status")
@safe_session
def check_build_status(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    status = building_system.get_building_status(p)
    if not status:
        return bot.answer_callback_query(call.id, "❌ لا يوجد بناء قيد التنفيذ")
    if status["is_complete"]:
        success, msg = building_system.complete_stage(p)
        if success:
            p.house_type = status["house_type"]
            session.commit()
        edit_msg(bot, call.message.chat.id, call.message.message_id, msg)
        return
    
    progress_bar = '█' * (status['progress']//10) + '░' * (10 - status['progress']//10)
    txt = f"🏗️ جارٍ البناء...\n"
    txt += f"🏠 البيت: {status['house_name']}\n"
    txt += f"📌 المرحلة: {status['stage_name']}\n"
    txt += f"📊 التقدم: {progress_bar} {status['progress']}%\n"
    txt += f"⏳ الوقت المتبقي: {status['time_left_str']}\n"
    
    if status['progress'] < 30:
        txt += "🔄 بداية العمل..."
    elif status['progress'] < 60:
        txt += "⚒️ جارٍ البناء..."
    elif status['progress'] < 90:
        txt += "🔨 يقترب من الانتهاء..."
    else:
        txt += "🎉 يكاد ينجز!"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="build_status"))
    kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="build_cancel"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "build_cancel")
@safe_session
def cancel_build(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if p.user_id in building_system.building_progress:
        del building_system.building_progress[p.user_id]
        session.commit()
        edit_msg(bot, call.message.chat.id, call.message.message_id, "❌ تم إلغاء البناء")
    else:
        bot.answer_callback_query(call.id, "❌ لا يوجد بناء قيد التنفيذ")

# Callbacks للقرية
@bot.callback_query_handler(func=lambda c: c.data == "v_sleep")
@safe_session
def village_sleep(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    result = gm.sleep(p)
    session.commit()
    if "error" in result:
        bot.answer_callback_query(call.id, result["error"])
    else:
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"😴 نمت جيداً!\n❤️ {result['hp']} | 🍖 {result['hunger']}")

@bot.callback_query_handler(func=lambda c: c.data == "v_quests")
@safe_session
def village_quests_menu(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    quests = [
        {"name": "الفلاح", "item": "wheat", "amount": 5, "reward": "bread", "reward_amt": 3, "xp": 10},
        {"name": "الحداد", "item": "iron_ore", "amount": 3, "reward": "iron_sword", "reward_amt": 1, "xp": 15},
        {"name": "الصياد", "item": "feather", "amount": 8, "reward": "bow", "reward_amt": 1, "xp": 12},
        {"name": "المستكشف", "item": "bone", "amount": 6, "reward": "gold_ore", "reward_amt": 3, "xp": 10},
        {"name": "البناء", "item": "stone", "amount": 10, "reward": "diamond", "reward_amt": 1, "xp": 20},
        {"name": "الساحر", "item": "sap", "amount": 4, "reward": "healing_potion", "reward_amt": 2, "xp": 15},
    ]
    q = random.choice(quests)
    txt = f"📋 **مهمة جديدة**\n\n👤 {q['name']} يطلب منك:\n📦 {q['item']} x{q['amount']}\n\n🎁 المكافأة: {q['reward']} x{q['reward_amt']}\n⭐ {q['xp']} XP"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✅ قبول المهمة", callback_data="quest_accept"))
    kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="back_to_village"))
    village_quests[call.from_user.id] = q
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "quest_accept")
@safe_session
def accept_quest(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in village_quests:
        return bot.answer_callback_query(call.id, "❌ لا توجد مهمة نشطة")
    q = village_quests[call.from_user.id]
    if p.has_item(q['item'], q['amount']):
        p.remove_item(q['item'], q['amount'])
        p.add_item(q['reward'], q['reward_amt'])
        p.add_xp(q['xp'])
        session.commit()
        del village_quests[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"✅ أكملت المهمة!\n🎁 {q['reward']} x{q['reward_amt']}\n⭐ +{q['xp']}XP")
    else:
        bot.answer_callback_query(call.id, f"❌ تحتاج {q['amount']} {q['item']}")

@bot.callback_query_handler(func=lambda c: c.data == "back_to_village")
@safe_session
def back_to_village(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    update_time_and_events(p)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("😴 نوم", callback_data="v_sleep"), types.InlineKeyboardButton("📋 مهام", callback_data="v_quests"))
    kb.add(types.InlineKeyboardButton("🛒 متجر", callback_data="v_shop"), types.InlineKeyboardButton("🏅 تبادل", callback_data="v_trade"))
    kb.add(types.InlineKeyboardButton("⚔️ بطل القرية", callback_data="v_champion"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"🏘️ القرية\n🕐 {p.get_time_of_day()}\n📊 مستوى القرية: {p.level//2 + 1}", kb)

@bot.callback_query_handler(func=lambda c: c.data == "v_shop")
@safe_session
def village_shop(call):
    session.rollback()
    txt = "🛒 **متجر القرية**\n\n"
    txt += "📦 تفاح = خشب بلوط ×2\n"
    txt += "📦 لحم = حديد خام ×1\n"
    txt += "📦 خبز = قمح ×3\n"
    txt += "💎 لؤلؤة إندر = ألماس ×2\n\n"
    txt += "استخدم /buy تفاح\n"
    txt += "استخدم /buy لحم\n"
    txt += "استخدم /buy خبز\n"
    txt += "استخدم /buy لؤلؤة"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "v_trade")
@safe_session
def village_trade(call):
    session.rollback()
    txt = "🏅 **التبادل مع القرويين**\n\n"
    txt += "1️⃣ فلاح: 5 قمح → 3 خبز\n"
    txt += "2️⃣ حداد: 3 حديد → 1 سيف حديدي\n"
    txt += "3️⃣ صياد: 8 ريش → 1 قوس\n"
    txt += "4️⃣ تاجر: 2 ألماس → 1 تفاح ذهبي\n\n"
    txt += "استخدم /trade 1\n"
    txt += "استخدم /trade 2\n"
    txt += "استخدم /trade 3\n"
    txt += "استخدم /trade 4"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "v_champion")
@safe_session
def village_champion(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if p.level >= 20:
        p.add_xp(10)
        p.add_item("diamond", 1)
        session.commit()
        edit_msg(bot, call.message.chat.id, call.message.message_id, "⚔️ **بطل القرية**\n\n🏅 أنت بطل القرية!\n⭐ مكافأة يومية: 10 XP + 1 ألماس")
    else:
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"⚔️ **بطل القرية**\n\n📊 تحتاج مستوى 20 لتصبح بطلاً\n📈 مستواك الحالي: {p.level}")

# Callbacks للحذف
@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
@safe_session
def delete_item(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    p.delete_slot(int(call.data.split("_")[1]))
    session.commit()
    bot.answer_callback_query(call.id, f"✅ تم حذف الخانة {int(call.data.split('_')[1])+1}")

# Callbacks للأكل
@bot.callback_query_handler(func=lambda c: c.data.startswith("eat_"))
@safe_session
def do_eat(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    res = gm.eat(p, call.data[4:])
    session.commit()
    if "error" in res:
        bot.answer_callback_query(call.id, res["error"])
    else:
        txt = f"🍖 {res['food']} | +{res['hunger']} شبع | {res['current']}/20"
        if res.get('effects'):
            txt += "\n" + "\n".join(res['effects'])
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

# Callbacks للمهارات
@bot.callback_query_handler(func=lambda c: c.data.startswith("sk_"))
@safe_session
def upgrade_skill(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    sk = call.data[3:]
    if p.skill_points > 0:
        setattr(p, sk, min(100, getattr(p, sk) + 1))
        if sk == "endurance":
            p.max_health += 2
            p.current_health += 2
        p.skill_points -= 1
        session.commit()
        bot.answer_callback_query(call.id, f"✅ {sk} +1")

# Callbacks للنذر
@bot.callback_query_handler(func=lambda c: c.data == "nether_enter")
@safe_session
def nether_enter(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    success, msg = nether.enter_nether(p)
    if success:
        kb = nether.get_nether_menu()
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"🔥 {msg}\n\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20", kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "nether_info")
@safe_session
def nether_info(call):
    session.rollback()
    txt = "🔥 **معلومات النذر**\n\n"
    txt += "📍 المستوى المطلوب: 10\n"
    txt += "💀 أعداء: أقوى من العالم العادي\n"
    txt += "🎁 مكافآت: نادرة وقوية\n"
    txt += "⚠️ خطر: الحمم والأعداء في كل مكان\n\n"
    txt += "**المعادن النادرة:**\n"
    txt += "⚫ خردة النذريت\n"
    txt += "🔥 عصا البلاز\n"
    txt += "💧 دمعة الغاست\n"
    txt += "🟠 كريم الماجما"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "nether_leave")
@safe_session
def nether_leave(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    success, msg = nether.leave_nether(p)
    bot.answer_callback_query(call.id, msg)
    go_back(call.message)

@bot.callback_query_handler(func=lambda c: c.data == "nether_inventory")
@safe_session
def nether_inventory(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        txt = "📭 المخزون فارغ"
    else:
        txt = "🎒 **مخزونك في النذر**\n\n"
        for idx, slot in items:
            txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, nether.get_nether_menu())

@bot.callback_query_handler(func=lambda c: c.data == "nether_status")
@safe_session
def nether_status(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    eq = p.get_equip()
    damage = gm.calc_damage(p)
    defense = gm.calc_defense(p)
    txt = f"🔥 **حالتك في النذر**\n\n"
    txt += f"👤 {p.username} | ⭐ Lv.{p.level}\n"
    txt += f"❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n"
    txt += f"🗡️ ضرر: {damage} | 🛡️ دفاع: {defense}\n"
    txt += f"⚔️ السلاح: {eq.get('weapon', 'لا يوجد')}"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, nether.get_nether_menu())

@bot.callback_query_handler(func=lambda c: c.data == "nether_explore")
@safe_session
def nether_explore_callback(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    if not p.in_nether:
        return bot.answer_callback_query(call.id, "❌ أنت لست في النذر!")
    
    if p.level < 10:
        return bot.answer_callback_query(call.id, "❌ تحتاج مستوى 10!")
    
    if p.current_health <= 5:
        return bot.answer_callback_query(call.id, "❤️ صحتك منخفضة! استرح قبل الاستكشاف!")
    
    events = nether.explore_nether(p)
    session.commit()
    
    txt = "🔥 **استكشاف النذر...**\n\n"
    
    for event in events:
        txt += f"{event['msg']}\n"
        if event.get('type') == 'enemy':
            battle_data = battle_system.start_battle(p, event['data'])
            battle_sessions[call.from_user.id] = battle_data
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"), types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend"))
            kb.add(types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run"))
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt + f"\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n❤️ العدو: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}", kb)
            return
    
    txt += f"\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20"
    
    if not events:
        txt += "\n🌋 النذر هادئ... لكن الحمم تغلي تحت قدميك!"
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, nether.get_nether_menu())

@bot.callback_query_handler(func=lambda c: c.data == "nether_stay")
@safe_session
def nether_stay(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    kb = nether.get_nether_menu()
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"🔥 **أنت في النذر!**\n\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20", kb)

# Callbacks للتنين
@bot.callback_query_handler(func=lambda c: c.data == "dragon_join_party")
@safe_session
def dragon_join_party_callback(call):
    p, _ = get_player(session, call.from_user.id)
    success, response = ender_dragon.join_fight(p)
    if success:
        status = ender_dragon.get_fight_status(p)
        bot.send_message(call.message.chat.id, f"{response}\n\n{status}")
    else:
        bot.answer_callback_query(call.id, response)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_fight")
@safe_session
def dragon_fight_callback(call):
    p, _ = get_player(session, call.from_user.id)
    success, msg = ender_dragon.start_dragon_fight(p)
    if success:
        status = ender_dragon.get_fight_status(p)
        bot.send_message(call.message.chat.id, f"{msg}\n\n{status}")
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_status")
@safe_session
def dragon_status_callback(call):
    p, _ = get_player(session, call.from_user.id)
    status = ender_dragon.get_fight_status(p)
    edit_msg(bot, call.message.chat.id, call.message.message_id, status)

# Callbacks للتوقف
@bot.callback_query_handler(func=lambda c: c.data == "stop")
@safe_session
def stop(call):
    session.rollback()
    uid = call.from_user.id
    chop_sessions.pop(uid, None)
    mine_sessions.pop(uid, None)
    battle_sessions.pop(uid, None)
    temple_puzzle_answers.pop(uid, None)
    village_quests.pop(uid, None)
    if uid in building_system.building_progress:
        del building_system.building_progress[uid]
    edit_msg(bot, call.message.chat.id, call.message.message_id, "👋 تم التوقف")

# ===============================
# 16. رايلوي - منفذ
# ===============================

def keep_alive():
    try:
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return "🤖 Minecraft Bot is running!"
        
        @app.route('/health')
        def health():
            return "OK", 200
        
        @app.route('/ping')
        def ping():
            return "PONG", 200
        
        @app.route('/time')
        def time_now():
            from datetime import datetime
            return datetime.now().isoformat()
        
        port = int(os.environ.get('PORT', 8080))
        print(f"🌐 Flask running on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"⚠️ Flask error: {e}")

# ===============================
# 17. تشغيل البوت
# ===============================

if __name__ == "__main__":
    print("="*50)
    print("🤖 Minecraft Bot is starting...")
    print("✅ Everything is ready!")
    print("🐉 Dragon system UPGRADED!")
    print("   • 300 HP (3x stronger)")
    print("   • 3 phases")
    print("   • 4 crystals/towers")
    print("   • Party fight system")
    print("   • Sword + Bow combat")
    print("✨ Inventory shows ALL items!")
    print("✨ All callbacks are written in full!")
    print("="*50)
    
    Thread(target=keep_alive, daemon=True).start()
    
    while True:
        try:
            print("✅ Bot polling started...")
            bot.infinity_polling(timeout=120, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ Polling error: {e}")
            print("🔄 Restarting in 10 seconds...")
            time.sleep(10)
            try:
                bot = telebot.TeleBot(TOKEN)
            except:
                pass
