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
            'temple_cooldown': 'TIMESTAMP'
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


import os, json, random, telebot, logging, time
from telebot import types
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from threading import Thread
from flask import Flask

# ===============================
# 0. نظام البناء (مُعدل مع تحسين عرض الوقت)
# ===============================

class BuildingSystem:
    BUILDING_STAGES = {
        "foundation": {
            "name": "🏗️ Foundation",
            "emoji": "🏗️",
            "resources": {"stone": 10, "oak_wood": 5},
            "time": 30,
            "next": "walls"
        },
        "walls": {
            "name": "🧱 Walls",
            "emoji": "🧱",
            "resources": {"stone": 20, "oak_wood": 10, "iron_ore": 2},
            "time": 45,
            "next": "roof"
        },
        "roof": {
            "name": "🏠 Roof",
            "emoji": "🏠",
            "resources": {"oak_wood": 15, "stone": 10, "spruce_wood": 5},
            "time": 40,
            "next": "doors"
        },
        "doors": {
            "name": "🚪 Doors",
            "emoji": "🚪",
            "resources": {"oak_wood": 6, "iron_ore": 2, "crafting_table": 1},
            "time": 25,
            "next": "windows"
        },
        "windows": {
            "name": "🪟 Windows",
            "emoji": "🪟",
            "resources": {"glass": 8, "iron_ore": 2, "stone": 4},
            "time": 35,
            "next": "complete"
        }
    }
    
    HOUSE_TYPES = {
        "wooden": {
            "name": "🏠 Wooden House",
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
            "name": "🏰 Stone House",
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
            "name": "🏛️ Mansion",
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
            return False, "❌ Unknown house type"
        first_stage = house["stages"][0]
        resources = house["resources"].get(first_stage, {})
        for item, amt in resources.items():
            if not player.has_item(item, amt):
                return False, f"❌ You need {amt} {item} for the first stage"
        return True, "✅ You can start building"
    
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
        return True, f"🏗️ Started building {house['name']}!\nStage: {self.BUILDING_STAGES[first_stage]['name']}\n⏳ Wait {self.BUILDING_STAGES[first_stage]['time']} seconds"
    
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
        time_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
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
            return False, "❌ No building in progress"
        progress = self.building_progress[player.user_id]
        status = self.get_building_status(player)
        if not status["is_complete"]:
            return False, f"⏳ Wait {status['time_left']} seconds to complete this stage"
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
            return True, f"🎉 {house['name']} completed!\n\nRewards:\n❤️ +{bonus.get('health', 0)} Health\n🛡️ +{bonus.get('defense', 0)} Defense\n🍀 +{bonus.get('luck', 0)} Luck"
        next_stage = stages[stage_index + 1]
        progress["current_stage"] = next_stage
        progress["stage_index"] = stage_index + 1
        progress["started_at"] = datetime.utcnow()
        house = self.HOUSE_TYPES[progress["house_type"]]
        resources = house["resources"].get(next_stage, {})
        for item, amt in resources.items():
            if not player.has_item(item, amt):
                return False, f"❌ Not enough resources for next stage\nNeed: {item} x{amt}"
            player.remove_item(item, amt)
        stage_info = self.BUILDING_STAGES[next_stage]
        self.session.commit()
        return True, f"✅ {self.BUILDING_STAGES[stages[stage_index]]['name']} completed!\n\n🏗️ Next stage: {stage_info['name']}\n⏳ Wait {stage_info['time']} seconds"

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
            return "🌅 Dawn"
        elif self.game_time < 60:
            return "☀️ Morning"
        elif self.game_time < 120:
            return "🌤️ Noon"
        elif self.game_time < 140:
            return "🌅 Sunset"
        elif self.game_time < 180:
            return "🌆 Evening"
        else:
            return "🌙 Night"
    
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
        titles_map = {10: "Beginner", 20: "Explorer", 30: "Warrior", 40: "Hunter", 50: "Builder", 60: "Wizard", 70: "Hero", 80: "Legend"}
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
    print("✅ Database connected successfully")
except Exception as e:
    print(f"❌ Error: {e}")
    DATABASE_URL = 'sqlite:///mc.db'
    engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    print("✅ SQLite database ready")

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
# 3. بيانات العالم (جميع الموارد بالإنجليزية)
# ===============================

class WorldData:
    @staticmethod
    def get_trees():
        return [
            {"name": "Oak Tree", "emoji": "🌳", "blocks": 8, "resources": [("oak_wood", 1)], "rare": ("apple", 1, 0.2), "break_time": 2},
            {"name": "Spruce Tree", "emoji": "🌲", "blocks": 10, "resources": [("spruce_wood", 1)], "rare": ("mushroom", 1, 0.2), "break_time": 2},
            {"name": "Birch Tree", "emoji": "🪵", "blocks": 7, "resources": [("birch_wood", 1)], "rare": ("sap", 1, 0.15), "break_time": 2},
            {"name": "Jungle Tree", "emoji": "🌴", "blocks": 12, "resources": [("jungle_wood", 1)], "rare": ("tropical_fruit", 1, 0.1), "break_time": 2.5},
        ]
    
    @staticmethod
    def get_rocks():
        return [
            {"name": "Stone", "emoji": "🪨", "blocks": 6, "resources": [("stone", 1)], "break_time": 3},
            {"name": "Coal Ore", "emoji": "🖤", "blocks": 8, "resources": [("stone", 1), ("coal", 1)], "break_time": 3},
            {"name": "Iron Ore", "emoji": "⛏️", "blocks": 10, "resources": [("stone", 1), ("iron_ore", 1)], "break_time": 4},
            {"name": "Gold Ore", "emoji": "✨", "blocks": 12, "resources": [("stone", 1), ("gold_ore", 1)], "rare": ("diamond", 1, 0.03), "break_time": 5},
            {"name": "Diamond Ore", "emoji": "💎", "blocks": 15, "resources": [("stone", 1), ("diamond", 1)], "rare": ("emerald", 1, 0.02), "break_time": 6},
        ]
    
    @staticmethod
    def get_animals():
        return {
            "Cow 🐄": [("leather", 2), ("raw_beef", 3), ("milk", 1)],
            "Pig 🐷": [("raw_pork", 3), ("bone", 2)],
            "Chicken 🐔": [("raw_chicken", 2), ("feather", 3), ("egg", 2)],
            "Sheep 🐑": [("wool", 3), ("raw_mutton", 2)],
            "Horse 🐴": [("saddle", 1), ("hoof", 2)],
            "Wolf 🐺": [("bone", 2)],
            "Bear 🐻": [("bear_meat", 3), ("bear_pelt", 2)],
        }
    
    @staticmethod
    def get_enemies(is_night=False):
        if is_night:
            return [
                {"name": "Zombie", "emoji": "🧟", "hp": 15, "damage": 6, "xp": 12, "drops": [("rotten_flesh", 2, 0.6)]},
                {"name": "Skeleton", "emoji": "💀", "hp": 18, "damage": 8, "xp": 15, "drops": [("bone", 3, 0.7), ("arrow", 3, 0.5)]},
                {"name": "Creeper", "emoji": "💚", "hp": 22, "damage": 14, "xp": 22, "drops": [("gunpowder", 3, 0.8)], "special": "explode"},
                {"name": "Iron Zombie", "emoji": "🧟‍♂️", "hp": 25, "damage": 10, "xp": 18, "drops": [("iron_ore", 2, 0.4)]},
                {"name": "Ghoul", "emoji": "👹", "hp": 35, "damage": 16, "xp": 30, "drops": [("gold_ore", 3, 0.5), ("diamond", 1, 0.15)]},
            ]
        else:
            return [
                {"name": "Wolf", "emoji": "🐺", "hp": 10, "damage": 4, "xp": 6, "drops": [("bone", 2, 0.5)], "special": "tameable"},
                {"name": "Bear", "emoji": "🐻", "hp": 25, "damage": 9, "xp": 18, "drops": [("bear_meat", 2, 0.8), ("bear_pelt", 1, 0.4)]},
                {"name": "Spider", "emoji": "🕷️", "hp": 12, "damage": 5, "xp": 8, "drops": [("spider_silk", 2, 0.5), ("spider_eye", 1, 0.3)]},
            ]
    
    @staticmethod
    def get_random_event(is_night):
        if is_night:
            events = [
                {"type": "loot", "msg": "🌙 Found a chest in the dark!", "item": random.choice(["coal", "iron_ore", "gold_ore"]), "amount": random.randint(2, 4)},
                {"type": "loot", "msg": "🕯️ A lit torch!", "item": "torch", "amount": random.randint(4, 8)},
            ]
        else:
            events = [
                {"type": "loot", "msg": "🎁 Found a gift on the ground!", "item": random.choice(["apple", "bread", "coal", "feather"]), "amount": random.randint(2, 4)},
                {"type": "loot", "msg": "🍯 A beehive!", "item": "honey", "amount": random.randint(3, 6)},
            ]
        return random.choice(events) if random.random() < 0.25 else None
    
    @staticmethod
    def get_temple_events():
        return {
            "puzzles": [
                {"q": "What walks on four legs in the morning, two in the afternoon, and three in the evening?", "a": "man", "reward": "apple", "amount": 5},
                {"q": "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?", "a": "echo", "reward": "gold_ore", "amount": 2},
                {"q": "I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?", "a": "map", "reward": "diamond", "amount": 1},
                {"q": "What has keys but can't open locks?", "a": "piano", "reward": "coal", "amount": 8},
            ],
            "monsters": [
                {"name": "Temple Guardian", "emoji": "🗿", "hp": 40, "damage": 12, "xp": 35, "drops": [("gold_ore", 5, 0.8), ("diamond", 2, 0.3)]},
                {"name": "Temple Demon", "emoji": "👿", "hp": 30, "damage": 15, "xp": 28, "drops": [("emerald", 3, 0.5), ("gold_ore", 4, 0.6)]},
                {"name": "Baby Dragon", "emoji": "🐉", "hp": 50, "damage": 18, "xp": 45, "drops": [("diamond", 3, 0.4), ("gold_ore", 8, 0.7)]},
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
            {"name": "Wooden Planks", "emoji": "🪵", "in": {"oak_wood": 1}, "out": {"wooden_planks": 4}, "xp": 1},
            {"name": "Sticks", "emoji": "🥢", "in": {"wooden_planks": 2}, "out": {"sticks": 4}, "xp": 1},
            {"name": "Crafting Table", "emoji": "🔨", "in": {"wooden_planks": 4}, "out": {"crafting_table": 1}, "xp": 2},
            {"name": "Furnace", "emoji": "🔥", "in": {"stone": 8}, "out": {"furnace": 1}, "xp": 2},
        ],
        "level_2": [
            {"name": "Wooden Axe", "emoji": "🪓", "in": {"wooden_planks": 3, "sticks": 2}, "out": {"wooden_axe": 1}, "xp": 3},
            {"name": "Wooden Sword", "emoji": "🗡️", "in": {"wooden_planks": 2, "sticks": 1}, "out": {"wooden_sword": 1}, "xp": 3},
            {"name": "Fence", "emoji": "🚧", "in": {"sticks": 6}, "out": {"fence": 3}, "xp": 1},
            {"name": "Wooden Door", "emoji": "🚪", "in": {"wooden_planks": 6}, "out": {"wooden_door": 1}, "xp": 2},
            {"name": "Wooden Helmet", "emoji": "🪖", "in": {"wooden_planks": 5}, "out": {"wooden_helmet": 1}, "xp": 3},
            {"name": "Wooden Chestplate", "emoji": "👕", "in": {"wooden_planks": 8}, "out": {"wooden_chestplate": 1}, "xp": 4},
        ],
        "level_3": [
            {"name": "Stone Axe", "emoji": "🪓", "in": {"stone": 3, "sticks": 2}, "out": {"stone_axe": 1}, "xp": 5},
            {"name": "Stone Sword", "emoji": "🗡️", "in": {"stone": 2, "sticks": 1}, "out": {"stone_sword": 1}, "xp": 5},
            {"name": "Stone Pickaxe", "emoji": "⛏️", "in": {"stone": 3, "sticks": 2}, "out": {"stone_pickaxe": 1}, "xp": 5},
            {"name": "Stone Helmet", "emoji": "🪖", "in": {"stone": 5}, "out": {"stone_helmet": 1}, "xp": 5},
            {"name": "Stone Chestplate", "emoji": "👕", "in": {"stone": 8}, "out": {"stone_chestplate": 1}, "xp": 6},
            {"name": "Bread", "emoji": "🍞", "in": {"wheat": 3}, "out": {"bread": 1}, "xp": 2},
        ],
        "level_4": [
            {"name": "Iron Pickaxe", "emoji": "⛏️", "in": {"iron_ore": 3, "sticks": 2}, "out": {"iron_pickaxe": 1}, "xp": 7},
            {"name": "Iron Sword", "emoji": "🗡️", "in": {"iron_ore": 2, "sticks": 1}, "out": {"iron_sword": 1}, "xp": 8},
            {"name": "Iron Helmet", "emoji": "🪖", "in": {"iron_ore": 5}, "out": {"iron_helmet": 1}, "xp": 8},
            {"name": "Iron Chestplate", "emoji": "👕", "in": {"iron_ore": 8}, "out": {"iron_chestplate": 1}, "xp": 10},
            {"name": "Iron Leggings", "emoji": "👖", "in": {"iron_ore": 7}, "out": {"iron_leggings": 1}, "xp": 9},
            {"name": "Iron Boots", "emoji": "👢", "in": {"iron_ore": 4}, "out": {"iron_boots": 1}, "xp": 7},
            {"name": "Bow", "emoji": "🏹", "in": {"sticks": 3, "spider_silk": 3}, "out": {"bow": 1}, "xp": 4},
            {"name": "Healing Potion", "emoji": "🧪", "in": {"sap": 2, "mushroom": 1}, "out": {"healing_potion": 1}, "xp": 8},
        ],
        "level_5": [
            {"name": "Diamond Axe", "emoji": "🪓", "in": {"diamond": 3, "sticks": 2}, "out": {"diamond_axe": 1}, "xp": 12},
            {"name": "Diamond Sword", "emoji": "🗡️", "in": {"diamond": 2, "sticks": 1}, "out": {"diamond_sword": 1}, "xp": 15},
            {"name": "Diamond Pickaxe", "emoji": "⛏️", "in": {"diamond": 3, "sticks": 2}, "out": {"diamond_pickaxe": 1}, "xp": 12},
            {"name": "Fire Chestplate", "emoji": "🔥", "in": {"fiery_coal": 5, "iron_ore": 8}, "out": {"fire_chestplate": 1}, "xp": 18},
            {"name": "Eye of Ender", "emoji": "👁️", "in": {"ender_pearl": 1, "blaze_rod": 1}, "out": {"eye_of_ender": 1}, "xp": 10},
            {"name": "Elytra", "emoji": "🪽", "in": {"diamond": 1, "feather": 10}, "out": {"elytra": 1}, "xp": 25},
            {"name": "Golden Apple", "emoji": "🍎", "in": {"apple": 1, "gold_ore": 8}, "out": {"golden_apple": 1}, "xp": 15},
            {"name": "Diamond Helmet", "emoji": "🪖", "in": {"diamond": 5}, "out": {"diamond_helmet": 1}, "xp": 15},
            {"name": "Diamond Chestplate", "emoji": "👕", "in": {"diamond": 8}, "out": {"diamond_chestplate": 1}, "xp": 18},
            {"name": "Diamond Leggings", "emoji": "👖", "in": {"diamond": 7}, "out": {"diamond_leggings": 1}, "xp": 16},
            {"name": "Diamond Boots", "emoji": "👢", "in": {"diamond": 4}, "out": {"diamond_boots": 1}, "xp": 14},
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
                return False, f"❌ You need {amt} {item}"
        for item, amt in recipe["in"].items():
            player.remove_item(item, amt)
        for item, amt in recipe["out"].items():
            player.add_item(item, amt)
        player.add_xp(recipe["xp"])
        return True, f"✅ Crafted {recipe['name']}! +{recipe['xp']}XP"
    
    @classmethod
    def furnace_smelt(cls, player, item_name):
        if item_name not in cls.FURNACE_RECIPES:
            return False, "❌ This item cannot be smelted"
        if not player.has_item("furnace"):
            return False, "❌ You need a furnace!"
        recipe = cls.FURNACE_RECIPES[item_name]
        if not player.has_item(item_name):
            return False, f"❌ You don't have {item_name}"
        if not player.has_item(recipe["fuel"], recipe["fuel_amt"]):
            return False, f"❌ You need {recipe['fuel']} x{recipe['fuel_amt']} as fuel"
        player.remove_item(item_name, 1)
        player.remove_item(recipe["fuel"], recipe["fuel_amt"])
        player.add_item(recipe["out"], 1)
        player.add_xp(3)
        return True, f"🔥 Smelted {item_name} → {recipe['out']}! +3XP"

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
            rewards.append("💔 You hurt your hand!")
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
            return {"rewards": ["❌ You need a pickaxe to break stone!"], "hunger": player.current_hunger, "health": player.current_health, "xp": 0, "failed": True}
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
            rewards.append("💔 You hurt yourself!")
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
            return {"error": "❌ You need a sword or bow to hunt!\nUse /equip iron_sword"}
        loot = WorldData.get_animals().get(animal_name)
        if not loot:
            return {"error": "Unknown animal"}
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
            rewards.append("💔 The animal hurt you!")
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
            return {"error": "Unknown food"}
        if not player.has_item(food):
            return {"error": "You don't have this food"}
        player.remove_item(food)
        val = food_db[food]
        if player.is_night():
            val = int(val * 0.8)
        player.current_hunger = min(player.max_hunger, player.current_hunger + val)
        effects = []
        if food == "golden_apple":
            player.current_health = min(player.max_health, player.current_health + 6)
            effects.append("💚 Golden apple heals you!")
        if "raw" in food and random.random() < 0.3:
            effects.append("⚠️ Food poisoning")
            player.current_health = max(0, player.current_health - 3)
        self.session.commit()
        return {"food": food, "hunger": val, "current": player.current_hunger, "effects": effects}
    
    def sleep(self, player):
        if not player.can_sleep():
            left = 12 - (datetime.utcnow() - player.last_sleep).seconds // 3600
            return {"error": f"⏳ Wait {left} hours"}
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        player.last_sleep = datetime.utcnow()
        player.game_time = 0
        self.session.commit()
        return {"msg": "😴 You slept well!", "hp": player.current_health, "hunger": player.current_hunger}

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
            'log': [f"⚔️ Battle started with {enemy['emoji']} {enemy['name']}!"],
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
            battle_data['log'].append("💥 Critical hit!")
        enemy_defense = random.randint(0, 2)
        final_damage = max(1, base_damage - enemy_defense)
        battle_data['enemy_hp'] = max(0, battle_data['enemy_hp'] - final_damage)
        battle_data['log'].append(f"🗡️ You hit {enemy['name']} for {final_damage} damage")
        battle_data['player_defending'] = False
        return battle_data
    
    def player_defend(self, player, battle_data):
        shield = 5 if not battle_data['is_night'] else 3
        battle_data['player_defending'] = True
        battle_data['log'].append(f"🛡️ You prepared to defend (+{shield} armor)")
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
            battle_data['log'].append(f"💥 {enemy['name']} exploded!")
        final_damage = max(0, enemy_damage - player_defense)
        if final_damage > 0:
            battle_data['player_hp'] = max(0, battle_data['player_hp'] - final_damage)
            battle_data['log'].append(f"💢 {enemy['name']} hit you for {final_damage} damage")
        else:
            battle_data['log'].append(f"🛡️ You blocked {enemy['name']}'s attack!")
        return battle_data
    
    def try_escape(self, player, battle_data):
        chance = 30 + player.speed
        if battle_data['is_night']:
            chance = int(chance * 0.6)
        if battle_data['round'] > 2:
            chance -= battle_data['round'] * 3
        chance = max(10, min(80, chance))
        if random.random() * 100 < chance:
            battle_data['log'].append("🏃 You escaped successfully!")
            return True, battle_data
        else:
            battle_data['log'].append("🚫 Failed to escape!")
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
            battle_data['log'].append(f"🎉 You defeated {enemy['name']}!")
            battle_data['log'].append(f"⭐ +{xp_reward} XP")
            if drops_text:
                battle_data['log'].append(f"📦 {', '.join(drops_text)}")
            self.session.commit()
            return 'win', battle_data
        if battle_data['player_hp'] <= 0:
            battle_data['log'].append("💀 You died!")
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
            return False, f"⏳ Temple is closed! Wait {remaining//60} minutes"
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
            return True, f"✅ Correct answer! You got {puzzle['reward']} x{puzzle['amount']} +10XP"
        else:
            damage = random.randint(3, 8)
            player.current_health = max(0, player.current_health - damage)
            self.session.commit()
            return False, f"❌ Wrong answer! You took {damage} damage"
    
    def get_temple_reward(self, player, treasure):
        player.add_item(treasure["item"], treasure["amount"])
        player.add_xp(15)
        player.temples_visited = (player.temples_visited or 0) + 1
        player.temple_cooldown = datetime.utcnow()
        self.session.commit()
        return f"🎁 You found treasure! {treasure['item']} x{treasure['amount']} +15XP"
    
    def get_temple_menu(self):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🔍 Explore", callback_data="temple_explore"),
            types.InlineKeyboardButton("🚪 Leave", callback_data="temple_leave")
        )
        return kb

# ===============================
# 8. نظام التنين المتطور 🐉🔥
# ===============================

class EnderDragonSystem:
    def __init__(self, session):
        self.session = session
        self.dragon_active = False
        self.dragon_hp = 0
        self.dragon_max_hp = 300  # 🔥 أقوى بــ 3 مرات
        self.fighters = {}
        self.dragon_spawn_time = None
        self.max_fighters = 3  # 👈 حد أقصى 3 مقاتلين
        
        # 🗼 نظام الأبراج
        self.towers = {
            1: {"name": "Fire Tower", "emoji": "🔥", "hp": 50, "max_hp": 50, "active": True},
            2: {"name": "Ice Tower", "emoji": "❄️", "hp": 50, "max_hp": 50, "active": True},
            3: {"name": "Lightning Tower", "emoji": "⚡", "hp": 50, "max_hp": 50, "active": True},
            4: {"name": "Dark Tower", "emoji": "🌑", "hp": 50, "max_hp": 50, "active": True},
        }
        self.towers_destroyed = 0
        self.combo_system = {}
        self.battle_phrases = [
            "⚔️ **Victory awaits!**",
            "🔥 **Unleash your power!**",
            "💥 **Crush the dragon!**",
            "🛡️ **Stand your ground!**",
            "⭐ **This is your moment!**",
            "🌊 **Like a tsunami of power!**",
            "⚡ **Strike like lightning!**",
            "🦅 **Soar high!**",
            "🏹 **Bullseye!**",
            "🗡️ **Sword of justice!**",
        ]
    
    def can_fight_dragon(self, player):
        if player.level < 20:
            return False, "❌ You need level 20 to fight the dragon!"
        if not player.has_item("eye_of_ender", 3):
            return False, "❌ You need 3 Eyes of Ender to open the portal!"
        
        # ✅ التحقق من السيف الألماسي (مخزون أو مجهز)
        has_sword = player.has_item("diamond_sword")
        if not has_sword:
            eq = player.get_equip()
            if eq.get("weapon") == "diamond_sword":
                has_sword = True
            elif eq.get("weapon") and "diamond_sword" in eq.get("weapon"):
                has_sword = True
        
        if not has_sword:
            return False, "❌ You need a diamond sword to fight the dragon!\n💡 Make sure you have it in inventory or equip it with /equip diamond_sword"
        
        if not player.has_item("bow"):
            return False, "❌ You need a bow to fight the dragon!"
        
        # التحقق من وجود سهام
        if not player.has_item("arrow", 1):
            return False, "❌ You need at least one arrow for the bow!"
        
        if player.defeated_ender_dragon:
            return False, "✅ You already defeated the dragon! 🏆"
        
        if len(self.fighters) >= self.max_fighters:
            return False, f"❌ Battle is full! Maximum {self.max_fighters} fighters"
        
        return True, "✅ Ready to fight the dragon!"
    
    def get_tower_animation(self):
        """رسم الأبراج بشكل متحرك"""
        tower_lines = []
        for i in range(1, 5):
            tower = self.towers[i]
            if tower["active"]:
                hp_percent = (tower["hp"] / tower["max_hp"]) * 100
                if hp_percent > 70:
                    state = "🟩🟩🟩🟩🟩"
                elif hp_percent > 40:
                    state = "🟨🟨🟨⬜⬜"
                elif hp_percent > 10:
                    state = "🟧🟧⬜⬜⬜"
                else:
                    state = "🟥⬜⬜⬜⬜"
                tower_lines.append(f"{tower['emoji']} {tower['name']}: {state} {int(hp_percent)}%")
            else:
                tower_lines.append(f"{tower['emoji']} {tower['name']}: 💥 Destroyed!")
        return "\n".join(tower_lines)
    
    def start_dragon_fight(self, player):
        can, msg = self.can_fight_dragon(player)
        if not can:
            return False, msg
        
        # إزالة السيف من المخزون إذا كان موجود
        if player.has_item("diamond_sword"):
            player.remove_item("diamond_sword", 1)
        
        player.remove_item("eye_of_ender", 3)
        
        # تفعيل التنين
        if not self.dragon_active:
            self.dragon_active = True
            self.dragon_hp = self.dragon_max_hp
            self.dragon_spawn_time = datetime.utcnow()
            self.towers_destroyed = 0
            # إعادة تعيين الأبراج
            for tower in self.towers.values():
                tower["hp"] = tower["max_hp"]
                tower["active"] = True
            self.fighters = {}
        
        # إضافة المقاتل
        self.fighters[player.user_id] = {
            "damage_dealt": 0,
            "joined_at": datetime.utcnow(),
            "combo": 0
        }
        
        self.session.commit()
        
        # إشعار
        self.broadcast_to_fighters(f"⚔️ **{player.username} joined the battle!** ({len(self.fighters)}/{self.max_fighters})")
        
        towers_art = self.get_tower_animation()
        
        return True, f"""🐉 **The Ender Dragon appears!**

❤️ Health: {self.dragon_hp}/{self.dragon_max_hp}
🗼 **Towers:**
{towers_art}
👥 Fighters: {len(self.fighters)}/{self.max_fighters}

⚔️ Use /dragon_attack to attack with sword
🏹 Use /dragon_bow to attack with bow
🗼 Use /dragon_tower to destroy a tower with bow
🛡️ Use /dragon_defend to defend

⚠️ **Destroy the towers first to weaken the dragon!**"""
    
    def broadcast_to_fighters(self, message):
        """إرسال رسالة لجميع المقاتلين"""
        for fighter_id in self.fighters.keys():
            try:
                bot.send_message(fighter_id, f"📢 {message}")
            except Exception as e:
                print(f"⚠️ Could not send to {fighter_id}: {e}")
    
    def get_random_phrase(self):
        """جلب عبارة عشوائية حماسية"""
        return random.choice(self.battle_phrases)
    
    def tower_attack(self, player, tower_id):
        """هجوم على برج بالقوس والسهام 🏹"""
        if not self.dragon_active:
            return False, "❌ No dragon to fight!"
        
        if tower_id not in self.towers:
            return False, "❌ Tower not found!"
        
        tower = self.towers[tower_id]
        if not tower["active"]:
            return False, "❌ This tower is already destroyed!"
        
        # ✅ التحقق من وجود القوس والسهام
        if not player.has_item("bow"):
            return False, "❌ You need a bow to destroy towers!"
        
        if not player.has_item("arrow", 1):
            return False, "❌ You need at least one arrow for the bow!"
        
        # حساب الضرر على البرج
        base_damage = 8 + player.strength
        
        # استخدام سهم
        player.remove_item("arrow", 1)
        base_damage += 5
        
        # مكافأة الضربات المتتالية
        combo = self.combo_system.get(player.user_id, 0) + 1
        self.combo_system[player.user_id] = combo
        if combo >= 3:
            base_damage = int(base_damage * 1.5)
        
        # الضربة الحاسمة
        if random.random() < 0.15 + (player.luck / 100):
            base_damage *= 2
        
        tower["hp"] = max(0, tower["hp"] - base_damage)
        
        # تحديث ضرر المقاتل
        if player.user_id in self.fighters:
            self.fighters[player.user_id]["damage_dealt"] += base_damage
        
        phrase = self.get_random_phrase()
        
        if tower["hp"] <= 0:
            tower["active"] = False
            self.towers_destroyed += 1
            self.session.commit()
            
            # تأثير على التنين
            self.dragon_hp = max(0, self.dragon_hp - 20)
            
            # إشعار الجميع
            self.broadcast_to_fighters(f"🗼 **{tower['name']} destroyed!** -20 dragon health!")
            
            if self.towers_destroyed >= 4:
                return True, f"""🗼 **All towers destroyed!**

🔥 The dragon is weakened!
{phrase}

❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}
🏹 Your bow damage: {base_damage}
💥 Combo: {combo}"""
            
            return True, f"""🗼 **{tower['name']} destroyed!** 💥

{phrase}
❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}
🗼 Towers remaining: {4 - self.towers_destroyed}
🏹 Your bow damage: {base_damage}
💥 Combo: {combo}"""
        
        # البرج لم يدمّر بعد
        self.session.commit()
        
        towers_art = self.get_tower_animation()
        
        return True, f"""🏹 **Bow attack on {tower['name']}!**

{towers_art}

{phrase}
❤️ Tower health: {tower['hp']}/{tower['max_hp']}
❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}
🏹 Your bow damage: {base_damage}
💥 Combo: {combo}"""
    
    def dragon_attack(self, player):
        """هجوم بالسيف على التنين ⚔️"""
        if not self.dragon_active or self.dragon_hp <= 0:
            return False, "❌ No dragon to fight!"
        
        # التحقق من السلاح
        eq = player.get_equip()
        weapon = eq.get("weapon")
        
        # التأكد من أن السيف مجهز
        if not weapon or "diamond_sword" not in weapon:
            return False, "❌ You must equip the diamond sword! Use /equip diamond_sword"
        
        # حساب الضرر
        base_damage = 10 + player.strength
        base_damage += 12  # ضرر السيف الألماسي
        
        # مكافأة الضربات المتتالية
        combo = self.combo_system.get(player.user_id, 0) + 1
        self.combo_system[player.user_id] = combo
        if combo >= 3:
            base_damage = int(base_damage * 1.5)
        
        # الأبراج تعطي مكافأة
        destroyed_percent = self.towers_destroyed / 4
        if destroyed_percent > 0:
            base_damage = int(base_damage * (1 + destroyed_percent * 0.3))
        
        # الضربة الحاسمة
        if random.random() < 0.2 + (player.luck / 100):
            base_damage *= 2
            phrase = "💥 **Critical sword hit!**"
        else:
            phrase = self.get_random_phrase()
        
        self.dragon_hp = max(0, self.dragon_hp - base_damage)
        
        # تحديث ضرر المقاتل
        if player.user_id in self.fighters:
            self.fighters[player.user_id]["damage_dealt"] += base_damage
        
        # هجوم التنين على اللاعب
        dragon_damage = random.randint(10, 25)
        if self.towers_destroyed >= 4:
            dragon_damage = int(dragon_damage * 0.5)
        elif self.towers_destroyed >= 2:
            dragon_damage = int(dragon_damage * 0.7)
        
        player.current_health = max(0, player.current_health - dragon_damage)
        
        self.session.commit()
        
        if self.dragon_hp <= 0:
            return self.dragon_defeated(player)
        
        return True, f"""⚔️ **You strike the dragon with your sword!**

{phrase}
🗡️ Your sword damage: {base_damage}
💥 Combo: {combo}
💢 Dragon hits you: -{dragon_damage} health

❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}
❤️ Your health: {player.current_health}/{player.max_health}
🗼 Towers destroyed: {self.towers_destroyed}/4"""
    
    def dragon_bow_attack(self, player):
        """هجوم بالقوس على التنين 🏹"""
        if not self.dragon_active or self.dragon_hp <= 0:
            return False, "❌ No dragon to fight!"
        
        # التحقق من وجود القوس والسهام
        if not player.has_item("bow"):
            return False, "❌ You need a bow!"
        
        if not player.has_item("arrow", 1):
            return False, "❌ You need at least one arrow!"
        
        # حساب الضرر
        base_damage = 8 + player.strength
        
        # استخدام سهم
        player.remove_item("arrow", 1)
        base_damage += 5
        
        # مكافأة الضربات المتتالية
        combo = self.combo_system.get(player.user_id, 0) + 1
        self.combo_system[player.user_id] = combo
        if combo >= 3:
            base_damage = int(base_damage * 1.5)
        
        # الأبراج تعطي مكافأة
        destroyed_percent = self.towers_destroyed / 4
        if destroyed_percent > 0:
            base_damage = int(base_damage * (1 + destroyed_percent * 0.3))
        
        # الضربة الحاسمة
        if random.random() < 0.2 + (player.luck / 100):
            base_damage *= 2
            phrase = "💥 **Critical bow hit!**"
        else:
            phrase = self.get_random_phrase()
        
        self.dragon_hp = max(0, self.dragon_hp - base_damage)
        
        # تحديث ضرر المقاتل
        if player.user_id in self.fighters:
            self.fighters[player.user_id]["damage_dealt"] += base_damage
        
        # هجوم التنين على اللاعب
        dragon_damage = random.randint(10, 25)
        if self.towers_destroyed >= 4:
            dragon_damage = int(dragon_damage * 0.5)
        elif self.towers_destroyed >= 2:
            dragon_damage = int(dragon_damage * 0.7)
        
        player.current_health = max(0, player.current_health - dragon_damage)
        
        self.session.commit()
        
        if self.dragon_hp <= 0:
            return self.dragon_defeated(player)
        
        return True, f"""🏹 **You shoot an arrow at the dragon!**

{phrase}
🏹 Your bow damage: {base_damage}
💥 Combo: {combo}
💢 Dragon hits you: -{dragon_damage} health

❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}
❤️ Your health: {player.current_health}/{player.max_health}
🗼 Towers destroyed: {self.towers_destroyed}/4"""
    
    def dragon_defend(self, player):
        """الدفاع ضد هجوم التنين"""
        if not self.dragon_active:
            return False, "❌ No dragon to fight!"
        
        shield = 8 + (player.endurance // 2)
        if self.towers_destroyed >= 4:
            shield += 5
        
        # إعادة تعيين الكومبو عند الدفاع
        self.combo_system[player.user_id] = 0
        
        # التنين يهاجم لكن الدفاع يقلل الضرر
        dragon_damage = random.randint(8, 20)
        actual_damage = max(0, dragon_damage - shield)
        
        if actual_damage > 0:
            player.current_health = max(0, player.current_health - actual_damage)
            self.session.commit()
            return True, f"""🛡️ **You blocked the dragon's attack!**

🛡️ Your shield: +{shield}
💢 Actual damage: -{actual_damage}

❤️ Your health: {player.current_health}/{player.max_health}
❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}"""
        else:
            self.session.commit()
            return True, f"""🛡️ **You completely blocked the attack!**

{self.get_random_phrase()}
💪 Your shield: +{shield}
✅ No damage!

❤️ Your health: {player.current_health}/{player.max_health}
❤️ Dragon: {self.dragon_hp}/{self.dragon_max_hp}"""
    
    def dragon_defeated(self, player):
        """هزيمة التنين"""
        self.dragon_active = False
        player.defeated_ender_dragon = True
        player.add_xp(200)
        player.level += 3
        
        rewards = [
            ("diamond", 20),
            ("gold_ore", 40),
            ("ender_pearl", 10),
            ("dragon_head", 1),
            ("dragon_egg", 1),
            ("netherite_scrap", 5),
        ]
        rewards_text = []
        for item, amt in rewards:
            player.add_item(item, amt)
            rewards_text.append(f"{item} x{amt}")
        
        titles = player.titles if isinstance(player.titles, list) else json.loads(player.titles or '[]')
        if "🔥 Legendary Dragon Slayer" not in titles:
            titles.append("🔥 Legendary Dragon Slayer")
        player.titles = titles
        
        # مكافأة إضافية لكل مقاتل
        for fighter_id in self.fighters.keys():
            if fighter_id != player.user_id:
                try:
                    fighter, _ = get_player(self.session, fighter_id)
                    fighter.add_xp(100)
                    fighter.level += 1
                    fighter.add_item("diamond", 5)
                    self.session.commit()
                except:
                    pass
        
        self.session.commit()
        
        return True, f"""🎉 **You defeated the Legendary Ender Dragon!** 🐉

{self.get_random_phrase()}

⭐ **Rewards:**
{', '.join(rewards_text)}

⬆️ +3 Levels
🔥 +200 XP
🏅 New Title: Legendary Dragon Slayer

**🎁 Team Rewards:**
- Every fighter +100 XP
- Every fighter +1 Level
- Every fighter 5 Diamonds

**You are Minecraft Champions!** 🏆"""
    
    def get_dragon_status(self):
        """حالة التنين الحالية"""
        if not self.dragon_active:
            return "🐉 The dragon is sleeping...\n📊 Ready for a challenge!"
        
        towers_art = self.get_tower_animation()
        
        fighters_list = []
        for fighter_id, data in self.fighters.items():
            try:
                fighter, _ = get_player(self.session, fighter_id)
                combo = self.combo_system.get(fighter_id, 0)
                fighters_list.append(f"{fighter.username} (⚔️{data['damage_dealt']} | 💥{combo})")
            except:
                pass
        
        fighters_text = "\n".join(fighters_list) if fighters_list else "None"
        
        return f"""🐉 **Legendary Dragon Battle!**

❤️ Dragon Health: {self.dragon_hp}/{self.dragon_max_hp}
🗼 Towers Destroyed: {self.towers_destroyed}/4

👥 **Fighters:** ({len(self.fighters)}/{self.max_fighters})
{fighters_text}

⏳ Time: {int((datetime.utcnow() - self.dragon_spawn_time).total_seconds() / 60)} minutes

{towers_art}"""

# ===============================
# 9. نظام النذر (مُعدل)
# ===============================

class NetherSystem:
    NETHER_ITEMS = {
        "nether_wart": {"name": "Nether Wart", "emoji": "🌿"},
        "blaze_rod": {"name": "Blaze Rod", "emoji": "🔥"},
        "ghast_tear": {"name": "Ghast Tear", "emoji": "💧"},
        "magma_cream": {"name": "Magma Cream", "emoji": "🟠"},
        "netherite_scrap": {"name": "Netherite Scrap", "emoji": "⚫"},
        "gold_ore": {"name": "Gold Ore", "emoji": "✨"},
        "soul_sand": {"name": "Soul Sand", "emoji": "🟤"},
        "nether_brick": {"name": "Nether Brick", "emoji": "🧱"},
    }
    
    # أعداء النذر (أقوى)
    NETHER_MOBS = [
        {"name": "Blaze", "emoji": "🔥", "hp": 35, "damage": 14, "xp": 25, 
         "drops": [("blaze_rod", 2, 0.7), ("fiery_coal", 1, 0.3)]},
        {"name": "Ghast", "emoji": "👻", "hp": 45, "damage": 20, "xp": 35,
         "drops": [("ghast_tear", 1, 0.4), ("gunpowder", 4, 0.6)]},
        {"name": "Pig Zombie", "emoji": "🧟‍♂️", "hp": 40, "damage": 16, "xp": 30,
         "drops": [("gold_ore", 3, 0.6), ("rotten_flesh", 5, 0.8)]},
        {"name": "Hell Skeleton", "emoji": "💀", "hp": 30, "damage": 18, "xp": 25,
         "drops": [("nether_brick", 4, 0.7), ("bow", 1, 0.1)]},
        {"name": "Magma Cube", "emoji": "🟠", "hp": 25, "damage": 12, "xp": 20,
         "drops": [("magma_cream", 2, 0.6), ("fiery_coal", 1, 0.2)]},
        {"name": "Bedrazine (Boss)", "emoji": "👾", "hp": 70, "damage": 28, "xp": 55,
         "drops": [("netherite_scrap", 2, 0.5), ("diamond", 3, 0.3), ("blaze_rod", 5, 0.8)]},
    ]
    
    def __init__(self, session):
        self.session = session
    
    def enter_nether(self, player):
        if player.level < 10:
            return False, "❌ You need level 10 to enter the Nether!"
        if not player.has_item("eye_of_ender", 1):
            return False, "❌ You need an Eye of Ender to open the Nether portal!"
        player.remove_item("eye_of_ender", 1)
        player.in_nether = True
        self.session.commit()
        return True, "🔥 You entered the Nether! The dangerous hell world..."
    
    def leave_nether(self, player):
        player.in_nether = False
        self.session.commit()
        return True, "🌍 You returned to the Overworld!"
    
    def explore_nether(self, player):
        events = []
        
        # 35% قتال مع عدو
        if random.random() < 0.35:
            mob = random.choice(self.NETHER_MOBS)
            events.append({
                'type': 'enemy',
                'data': mob,
                'msg': f"⚔️ {mob['emoji']} {mob['name']} attacks you suddenly!"
            })
        
        # 25% كنز
        if random.random() < 0.25:
            item = random.choice(list(self.NETHER_ITEMS.values()))
            amt = random.randint(2, 5 + (player.luck or 0) // 5)
            player.add_item(item['name'], amt)
            events.append({
                'type': 'loot',
                'msg': f"🎁 You found a chest in the lava! {item['emoji']} {item['name']} x{amt}!"
            })
        
        # 15% فخ
        if random.random() < 0.15:
            damage = random.randint(5, 15)
            player.current_health = max(0, player.current_health - damage)
            events.append({
                'type': 'damage',
                'msg': f"💥 The lava floor exploded under you! -{damage} health"
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
                'msg': f"🌀 Secret portal! You found {reward['emoji']} {reward['name']} x{reward['amt']}!"
            })
        
        # 5% زعيم
        if random.random() < 0.05:
            boss = self.NETHER_MOBS[-1]
            events.append({
                'type': 'enemy',
                'data': boss,
                'msg': f"👾 **Bedrazine - Nether Boss appears!**\n⚔️ Prepare for battle!"
            })
        
        self.session.commit()
        return events
    
    def get_nether_menu(self):
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🔍 Explore", callback_data="nether_explore"),
            types.InlineKeyboardButton("📦 Inventory", callback_data="nether_inventory")
        )
        kb.add(
            types.InlineKeyboardButton("❤️ Status", callback_data="nether_status"),
            types.InlineKeyboardButton("🏃 Leave", callback_data="nether_leave")
        )
        return kb

# ===============================
# 10. رسم المنزل بمكعبات ماينكرافت
# ===============================

class MinecraftHouseDrawer:
    
    HOUSES = {
        "wooden": {
            "name": "Wooden House",
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
            "name": "Stone House",
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
            "name": "Mansion",
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
            "name": "Nether House",
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
            return "🏚️ No house"
        
        house = cls.HOUSES[house_type]
        layout = house["layout"]
        
        result = []
        if show_owner and owner_name:
            result.append(f"🏠 {house['name']} - Level {level}")
            result.append("")
        
        result.extend(layout)
        
        result.append("")
        result.append(f"📊 Level: {level}")
        result.append(f"👤 Owner: {owner_name if show_owner else 'Unknown'}")
        
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
                return f"""🏗️ **Building...** ({progress_percent}%)

🟫🟫🟫🟫🟫🟫🟫
🟫🟫⬜⬜⬜🟫🟫
🟫🟫⬜⬜⬜🟫🟫
🟫🟫⬜⬜⬜🟫🟫
🟫🟫🟫🟫🟫🟫🟫
🟩🟩🟩🟩🟩🟩🟩

⏳ Stage: {building_system.BUILDING_STAGES[progress['current_stage']]['name']}"""
        
        # إذا كان البيت مكتمل (من قاعدة البيانات)
        if player.house_type:
            return cls.draw_house(player.house_type, True, player.username, 1)
        
        return "🏚️ No house"

# ===============================
# 11. البوت (الكامل المُعدل)
# ===============================

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    print("❌ Token not found!")
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
                    bot.send_message(args[0].chat.id, "⚠️ Database error. Please try again.")
            except:
                pass
            raise
    return wrapper

def menu(player=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # إذا كان اللاعب في النذر
    if player and player.in_nether:
        kb.add("🔥 Nether")
        kb.add("🔙 Back")
        return kb
    
    # القائمة العادية (مع إضافة زر المساعدة)
    kb.add("🌳 Forest", "🕳️ Cave")
    kb.add("🏘️ Village", "🎒 Inventory")
    kb.add("🛠️ Crafting", "🏠 Build")
    kb.add("🍖 Eat", "🗑️ Delete")
    kb.add("❤️ Status", "📊 Skills")
    kb.add("🔥 Nether", "🐉 Dragon")
    kb.add("📖 Help", "🔙 Back")
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
        txt = "🌟 Welcome to Minecraft Bot!\n\nUse the buttons to navigate.\n📖 Press Help for instructions."
    else:
        tod = p.get_time_of_day()
        txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu(p))

# ===============================
# 12. زر المساعدة - دليل المستخدم الشامل 🆕
# ===============================

@bot.message_handler(func=lambda m: m.text == "📖 Help")
@safe_session
def help_menu(msg):
    """دليل المستخدم الشامل للعبة"""
    help_text = """
📖 **Minecraft Bot Guide** 🎮

━━━━━━━━━━━━━━━━━━━━━━

🌟 **Getting Started**
• Use buttons to navigate
• Start by gathering resources from Forest and Cave
• Your level increases with XP

━━━━━━━━━━━━━━━━━━━━━━

🌳 **Forest**
• Chop trees for wood
• Hunt animals for food and leather
• Exploring may reveal ancient temples

🕳️ **Cave**
• Mine rocks for minerals
• Stone → Coal → Iron → Gold → Diamond
• You need a pickaxe to mine!

━━━━━━━━━━━━━━━━━━━━━━

🏠 **Building**
• Level 1: Wooden House 🏠
• Level 5: Stone House 🏰
• Level 15: Mansion 🏛️
• Each house gives permanent bonuses

🛠️ **Crafting**
• Craft tools, weapons, and armor• Use furnace to smelt ores
• Unlock new recipes as you level up

━━━━━━━━━━━━━━━━━━━━━━

🔥 **Nether**
• Level 10+ to enter
• Need Eye of Ender for portal
• Strong enemies and rare rewards
• Netherite Scrap, Blaze Rods, and more

🐉 **Dragon** (NEW!)
• Level 20+ to fight
• Need 3 Eyes of Ender + Diamond Sword + Bow + Arrows
• Team battle (max 3 players)
• Destroy 4 towers with bow 🏹
• Huge rewards upon victory!

━━━━━━━━━━━━━━━━━━━━━━

🏘️ **Village**
• Sleep to restore health and hunger
• Daily quests for rewards
• Shop to buy resources
• Trade with villagers

━━━━━━━━━━━━━━━━━━━━━━

⚔️ **Combat**
• Use /equip to equip weapons
• Swords: Wooden → Stone → Iron → Diamond
• Armor protects from attacks
• Enemies are stronger at night!

━━━━━━━━━━━━━━━━━━━━━━

📊 **Skills**
• Every 5 levels you get a skill point
• Strength increases damage
• Speed helps with escape
• Endurance increases health
• Luck increases rare drops

━━━━━━━━━━━━━━━━━━━━━━

💡 **Tips**
• Keep your hunger high (🍖)
• Sleep in the village to heal
• Use the right tool for each job
• Save rare resources for advanced crafting
• Explore temples for treasures

━━━━━━━━━━━━━━━━━━━━━━

🔧 **Quick Commands**
/equip item_name - Equip an item
/additem item_name amount - Add item (developer)
/buy item_name - Buy from shop
/trade number - Trade with villager

━━━━━━━━━━━━━━━━━━━━━━

📱 **Suggestions welcome!**
Help us improve the game 🚀
"""
    
    # إضافة زر العودة مع الحالة الحالية
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu"))
    
    bot.send_message(msg.chat.id, help_text, reply_markup=kb, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda c: c.data == "back_to_menu")
@safe_session
def back_to_menu(call):
    """العودة للقائمة الرئيسية من المساعدة"""
    p, _ = get_player(session, call.from_user.id)
    tod = p.get_time_of_day()
    txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, menu(p))

# ===============================
# 13. باقي أوامر البوت (معدلة)
# ===============================

@bot.message_handler(commands=['additem'])
@safe_session
def add_item_cmd(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 3:
        return bot.send_message(msg.chat.id, "Use: /additem item_name amount")
    try:
        amt = int(args[2])
    except:
        return bot.send_message(msg.chat.id, "❌ Amount must be a number")
    
    # قائمة العناصر المسموحة (جميعها بالإنجليزية)
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
        return bot.send_message(msg.chat.id, f"❌ {args[1]} unknown!\nAvailable items: {', '.join(valid_items[:20])}...")
    
    p.add_item(args[1], amt)
    session.commit()
    bot.send_message(msg.chat.id, f"✅ Added {amt} of {args[1]}!")

# ===============================
# 14. نظام الحذف (36 خانة كاملة)
# ===============================

@bot.message_handler(func=lambda m: m.text == "🗑️ Delete")
@safe_session
def delete_menu(msg):
    """عرض جميع الخانات الـ 36 للحذف"""
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    
    # عرض جميع الخانات (0-35)
    txt = "🗑️ **Select item to delete:**\n\n"
    kb = types.InlineKeyboardMarkup(row_width=6)  # 6 أزرار في الصف
    
    for i in range(36):  # عرض جميع الخانات الـ 36
        slot = inv.get(f"slot_{i}")
        if slot:
            txt += f"`{i+1}`. {slot['name']} x{slot['amount']}\n"
            kb.add(types.InlineKeyboardButton(f"{i+1}", callback_data=f"del_{i}"))
        else:
            txt += f"`{i+1}`. 🟩 **Empty**\n"
    
    kb.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete"))
    
    bot.send_message(
        msg.chat.id, 
        txt, 
        reply_markup=kb,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
@safe_session
def delete_item(call):
    """حذف العنصر المختار"""
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    slot_num = int(call.data.split("_")[1])
    inv = p.get_inv()
    slot = inv.get(f"slot_{slot_num}")
    
    if not slot:
        return bot.answer_callback_query(call.id, "❌ This slot is already empty!", show_alert=True)
    
    item_name = slot.get("name")
    item_amount = slot.get("amount")
    
    p.delete_slot(slot_num)
    session.commit()
    
    bot.answer_callback_query(
        call.id, 
        f"✅ Deleted {item_name} x{item_amount} from slot {slot_num+1}",
        show_alert=True
    )
    
    # تحديث الرسالة
    edit_msg(
        bot, 
        call.message.chat.id, 
        call.message.message_id, 
        f"🗑️ **Deleted!**\n\n✅ Removed `{item_name}` x{item_amount}"
    )

@bot.callback_query_handler(func=lambda c: c.data == "cancel_delete")
@safe_session
def cancel_delete(call):
    """إلغاء عملية الحذف"""
    edit_msg(
        bot, 
        call.message.chat.id, 
        call.message.message_id, 
        "❌ Delete cancelled"
    )

# ===============================
# 15. باقي أوامر البوت
# ===============================

@bot.message_handler(func=lambda m: m.text == "🎒 Inventory")
@safe_session
def inventory(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.send_message(msg.chat.id, f"📭 Inventory empty\n🕐 {p.get_time_of_day()}")
    txt = f"🎒 Your Inventory\n🕐 {p.get_time_of_day()}\n\n"
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    if len(items) > 18:
        txt += f"\n... and {len(items)-18} more items"
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "🍖 Eat")
@safe_session
def eat_menu(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    foods = [s for s in inv.values() if s and s['name'] in ["apple", "bread", "cooked_beef", "honey", "golden_apple", "raw_beef", "tropical_fruit", "cooked_chicken", "cooked_pork", "cooked_mutton"]]
    if not foods:
        return bot.send_message(msg.chat.id, "🍖 No food")
    kb = types.InlineKeyboardMarkup(row_width=2)
    for f in foods[:10]:
        kb.add(types.InlineKeyboardButton(f"{f['name']} x{f['amount']}", callback_data=f"eat_{f['name']}"))
    bot.send_message(msg.chat.id, "🍖 Choose food", reply_markup=kb)

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
        txt = f"🍖 {res['food']} | +{res['hunger']} hunger | {res['current']}/20"
        if res.get('effects'):
            txt += "\n" + "\n".join(res['effects'])
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.message_handler(func=lambda m: m.text == "❤️ Status")
@safe_session
def status(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    titles = p.titles if isinstance(p.titles, list) else []
    eq = p.get_equip()
    damage = gm.calc_damage(p)
    defense = gm.calc_defense(p)
    
    # رسم المنزل
    house_art = MinecraftHouseDrawer.get_house_art(p)
    
    txt = f"👤 {p.username} | ⭐ Lv.{p.level}\n"
    txt += f"❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n"
    txt += f"🗡️ Damage: {damage} | 🛡️ Defense: {defense}\n"
    txt += f"🕐 {p.get_time_of_day()}\n"
    txt += f"⚔️ Weapon/Tool: {eq.get('weapon', 'None')}\n"
    txt += f"🪖 Helmet: {eq.get('helmet', 'None')}\n"
    txt += f"👕 Chestplate: {eq.get('chestplate', 'None')}\n"
    txt += f"👖 Leggings: {eq.get('leggings', 'None')}\n"
    txt += f"👢 Boots: {eq.get('boots', 'None')}\n"
    txt += f"\n🏠 **Your House:**\n{house_art}\n"
    txt += f"🏅 {', '.join(titles) if titles else 'No titles'}\n"
    txt += f"🐺 Pet: {p.pet or 'None'}\n"
    txt += f"🏛️ Temples: {p.temples_visited or 0}\n"
    txt += f"🐉 Dragon: {'✅ Defeated' if p.defeated_ender_dragon else '❌ Not defeated'}"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📊 Skills")
@safe_session
def skills(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    txt = f"⚔️ Strength: {p.strength} | 💨 Speed: {p.speed}\n💪 Endurance: {p.endurance} | 🍀 Luck: {p.luck}\n🎯 Points: {p.skill_points}"
    if p.skill_points > 0:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("⚔️ Strength", callback_data="sk_strength"), types.InlineKeyboardButton("💨 Speed", callback_data="sk_speed"))
        kb.add(types.InlineKeyboardButton("💪 Endurance", callback_data="sk_endurance"), types.InlineKeyboardButton("🍀 Luck", callback_data="sk_luck"))
        bot.send_message(msg.chat.id, txt, reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, txt)

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

# ===============================
# 16. أوامر التنين 🐉
# ===============================

@bot.message_handler(func=lambda m: m.text == "🐉 Dragon")
@safe_session
def dragon_menu(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    status = ender_dragon.get_dragon_status()
    can, msg_text = ender_dragon.can_fight_dragon(p)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if ender_dragon.dragon_active:
        kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
        kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
        kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
        kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
        
        if len(ender_dragon.fighters) < ender_dragon.max_fighters:
            if can:
                kb.add(types.InlineKeyboardButton("⚔️ Join Battle!", callback_data="dragon_join"))
        
        kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
        kb.add(types.InlineKeyboardButton("🏃 Run", callback_data="dragon_run"))
    else:
        if can:
            kb.add(types.InlineKeyboardButton("🐉 Start Battle!", callback_data="dragon_start"))
        kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
    
    bot.send_message(msg.chat.id, f"{status}\n\n{msg_text}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_join")
@safe_session
def dragon_join(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    if not ender_dragon.dragon_active:
        return bot.answer_callback_query(call.id, "❌ No active dragon battle!")
    
    if p.user_id in ender_dragon.fighters:
        return bot.answer_callback_query(call.id, "✅ You're already in battle!")
    
    if len(ender_dragon.fighters) >= ender_dragon.max_fighters:
        return bot.answer_callback_query(call.id, f"❌ Battle is full! Maximum {ender_dragon.max_fighters} fighters")
    
    can, msg = ender_dragon.can_fight_dragon(p)
    if not can:
        return bot.answer_callback_query(call.id, msg)
    
    ender_dragon.fighters[p.user_id] = {
        "damage_dealt": 0,
        "joined_at": datetime.utcnow(),
        "combo": 0
    }
    session.commit()
    
    ender_dragon.broadcast_to_fighters(f"⚔️ **{p.username} joined the battle!** ({len(ender_dragon.fighters)}/{ender_dragon.max_fighters})")
    
    bot.answer_callback_query(call.id, f"✅ Joined battle! Fighters: {len(ender_dragon.fighters)}/{ender_dragon.max_fighters}")

@bot.callback_query_handler(func=lambda c: c.data == "dragon_tower_menu")
@safe_session
def dragon_tower_menu(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    if not ender_dragon.dragon_active:
        return bot.answer_callback_query(call.id, "❌ No dragon to fight!")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for tower_id, tower in ender_dragon.towers.items():
        if tower["active"]:
            hp_percent = (tower["hp"] / tower["max_hp"]) * 100
            kb.add(types.InlineKeyboardButton(
                f"{tower['emoji']} {tower['name']} ({int(hp_percent)}%)",
                callback_data=f"dragon_tower_{tower_id}"
            ))
    
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="dragon_back"))
    
    towers_art = ender_dragon.get_tower_animation()
    edit_msg(bot, call.message.chat.id, call.message.message_id, 
             f"🗼 **Choose a tower to destroy with bow 🏹:**\n\n{towers_art}", kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("dragon_tower_"))
@safe_session
def dragon_tower_attack(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    tower_id = int(call.data.split("_")[2])
    
    success, msg = ender_dragon.tower_attack(p, tower_id)
    if success:
        if "destroyed" in msg or "All" in msg:
            edit_msg(bot, call.message.chat.id, call.message.message_id, msg)
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
            kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
            kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
            kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
            kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
            edit_msg(bot, call.message.chat.id, call.message.message_id, msg, kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_bow")
@safe_session
def dragon_bow_attack_callback(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    success, msg = ender_dragon.dragon_bow_attack(p)
    if success:
        if "defeated" in msg or "victory" in msg:
            edit_msg(bot, call.message.chat.id, call.message.message_id, msg)
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
            kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
            kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
            kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
            kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
            edit_msg(bot, call.message.chat.id, call.message.message_id, msg, kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_back")
@safe_session
def dragon_back(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    status = ender_dragon.get_dragon_status()
    can, msg_text = ender_dragon.can_fight_dragon(p)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if ender_dragon.dragon_active:
        kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
        kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
        kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
        kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
        if len(ender_dragon.fighters) < ender_dragon.max_fighters:
            if can:
                kb.add(types.InlineKeyboardButton("⚔️ Join Battle!", callback_data="dragon_join"))
        kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
        kb.add(types.InlineKeyboardButton("🏃 Run", callback_data="dragon_run"))
    else:
        if can:
            kb.add(types.InlineKeyboardButton("🐉 Start Battle!", callback_data="dragon_start"))
        kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"{status}\n\n{msg_text}", kb)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_run")
@safe_session
def dragon_run(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    if p.user_id in ender_dragon.fighters:
        del ender_dragon.fighters[p.user_id]
        ender_dragon.broadcast_to_fighters(f"🏃 **{p.username} fled the battle!**")
        session.commit()
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, "🏃 You fled the battle!")
    go_back(call.message)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_start")
@safe_session
def dragon_start(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    success, msg = ender_dragon.start_dragon_fight(p)
    if success:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
        kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
        kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
        kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
        kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
        kb.add(types.InlineKeyboardButton("🏃 Run", callback_data="dragon_run"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, msg, kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_status")
@safe_session
def dragon_status_callback(call):
    session.rollback()
    edit_msg(bot, call.message.chat.id, call.message.message_id, ender_dragon.get_dragon_status())

@bot.callback_query_handler(func=lambda c: c.data == "dragon_attack")
@safe_session
def dragon_attack_callback(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    
    success, msg = ender_dragon.dragon_attack(p)
    if success:
        if "defeated" in msg or "victory" in msg:
            edit_msg(bot, call.message.chat.id, call.message.message_id, msg)
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
            kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
            kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
            kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
            kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
            edit_msg(bot, call.message.chat.id, call.message.message_id, msg, kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "dragon_defend")
@safe_session
def dragon_defend_callback(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    success, msg = ender_dragon.dragon_defend(p)
    if success:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("⚔️ Sword Attack", callback_data="dragon_attack"))
        kb.add(types.InlineKeyboardButton("🏹 Bow Attack", callback_data="dragon_bow"))
        kb.add(types.InlineKeyboardButton("🗼 Destroy Tower", callback_data="dragon_tower_menu"))
        kb.add(types.InlineKeyboardButton("🛡️ Defend", callback_data="dragon_defend"))
        kb.add(types.InlineKeyboardButton("📊 Dragon Status", callback_data="dragon_status"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, msg, kb)
    else:
        bot.answer_callback_query(call.id, msg)

# ===============================
# 17. أوامر القرية والمتجر
# ===============================

@bot.message_handler(func=lambda m: m.text == "🏘️ Village")
@safe_session
def village(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_events(p)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("😴 Sleep", callback_data="v_sleep"), types.InlineKeyboardButton("📋 Quests", callback_data="v_quests"))
    kb.add(types.InlineKeyboardButton("🛒 Shop", callback_data="v_shop"), types.InlineKeyboardButton("🏅 Trade", callback_data="v_trade"))
    kb.add(types.InlineKeyboardButton("⚔️ Village Champion", callback_data="v_champion"))
    bot.send_message(msg.chat.id, f"🏘️ Village\n🕐 {p.get_time_of_day()}\n📊 Village Level: {p.level//2 + 1}", reply_markup=kb)

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
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"😴 You slept well!\n❤️ {result['hp']} | 🍖 {result['hunger']}")

@bot.callback_query_handler(func=lambda c: c.data == "v_quests")
@safe_session
def village_quests_menu(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    quests = [
        {"name": "Farmer", "item": "wheat", "amount": 5, "reward": "bread", "reward_amt": 3, "xp": 10},
        {"name": "Blacksmith", "item": "iron_ore", "amount": 3, "reward": "iron_sword", "reward_amt": 1, "xp": 15},
        {"name": "Hunter", "item": "feather", "amount": 8, "reward": "bow", "reward_amt": 1, "xp": 12},
        {"name": "Explorer", "item": "bone", "amount": 6, "reward": "gold_ore", "reward_amt": 3, "xp": 10},
        {"name": "Builder", "item": "stone", "amount": 10, "reward": "diamond", "reward_amt": 1, "xp": 20},
        {"name": "Wizard", "item": "sap", "amount": 4, "reward": "healing_potion", "reward_amt": 2, "xp": 15},
    ]
    q = random.choice(quests)
    txt = f"📋 **New Quest**\n\n👤 {q['name']} asks for:\n📦 {q['item']} x{q['amount']}\n\n🎁 Reward: {q['reward']} x{q['reward_amt']}\n⭐ {q['xp']} XP"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("✅ Accept Quest", callback_data="quest_accept"))
    kb.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_village"))
    village_quests[call.from_user.id] = q
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "quest_accept")
@safe_session
def accept_quest(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in village_quests:
        return bot.answer_callback_query(call.id, "❌ No active quest")
    q = village_quests[call.from_user.id]
    if p.has_item(q['item'], q['amount']):
        p.remove_item(q['item'], q['amount'])
        p.add_item(q['reward'], q['reward_amt'])
        p.add_xp(q['xp'])
        session.commit()
        del village_quests[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"✅ Quest completed!\n🎁 {q['reward']} x{q['reward_amt']}\n⭐ +{q['xp']}XP")
    else:
        bot.answer_callback_query(call.id, f"❌ You need {q['amount']} {q['item']}")

@bot.callback_query_handler(func=lambda c: c.data == "back_to_village")
@safe_session
def back_to_village(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    update_time_and_events(p)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("😴 Sleep", callback_data="v_sleep"), types.InlineKeyboardButton("📋 Quests", callback_data="v_quests"))
    kb.add(types.InlineKeyboardButton("🛒 Shop", callback_data="v_shop"), types.InlineKeyboardButton("🏅 Trade", callback_data="v_trade"))
    kb.add(types.InlineKeyboardButton("⚔️ Village Champion", callback_data="v_champion"))
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"🏘️ Village\n🕐 {p.get_time_of_day()}\n📊 Village Level: {p.level//2 + 1}", kb)

@bot.callback_query_handler(func=lambda c: c.data == "v_shop")
@safe_session
def village_shop(call):
    session.rollback()
    txt = "🛒 **Village Shop**\n\n"
    txt += "📦 Apple = Oak Wood ×2\n"
    txt += "📦 Cooked Beef = Iron Ore ×1\n"
    txt += "📦 Bread = Wheat ×3\n"
    txt += "💎 Ender Pearl = Diamond ×2\n\n"
    txt += "Use /buy apple\n"
    txt += "Use /buy beef\n"
    txt += "Use /buy bread\n"
    txt += "Use /buy pearl"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.callback_query_handler(func=lambda c: c.data == "v_trade")
@safe_session
def village_trade(call):
    session.rollback()
    txt = "🏅 **Trade with Villagers**\n\n"
    txt += "1️⃣ Farmer: 5 Wheat → 3 Bread\n"
    txt += "2️⃣ Blacksmith: 3 Iron → 1 Iron Sword\n"
    txt += "3️⃣ Hunter: 8 Feathers → 1 Bow\n"
    txt += "4️⃣ Merchant: 2 Diamonds → 1 Golden Apple\n\n"
    txt += "Use /trade 1\n"
    txt += "Use /trade 2\n"
    txt += "Use /trade 3\n"
    txt += "Use /trade 4"
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
        edit_msg(bot, call.message.chat.id, call.message.message_id, "⚔️ **Village Champion**\n\n🏅 You are the Village Champion!\n⭐ Daily reward: 10 XP + 1 Diamond")
    else:
        edit_msg(bot, call.message.chat.id, call.message.message_id, f"⚔️ **Village Champion**\n\n📊 You need level 20 to become Champion\n📈 Your current level: {p.level}")

@bot.message_handler(commands=['buy'])
@safe_session
def buy(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 2:
        return bot.send_message(msg.chat.id, "❌ Use: /buy apple\n/buy beef\n/buy bread\n/buy pearl")
    
    shop = {
        "apple": {"price": "oak_wood", "amt": 2, "give": "apple", "gamt": 3},
        "beef": {"price": "iron_ore", "amt": 1, "give": "cooked_beef", "gamt": 1},
        "bread": {"price": "wheat", "amt": 3, "give": "bread", "gamt": 2},
        "pearl": {"price": "diamond", "amt": 2, "give": "ender_pearl", "gamt": 1},
    }
    
    item = args[1]
    if item not in shop:
        return bot.send_message(msg.chat.id, "❌ Item not available!\nAvailable: apple, beef, bread, pearl")
    
    s = shop[item]
    if p.has_item(s["price"], s["amt"]):
        p.remove_item(s["price"], s["amt"])
        p.add_item(s["give"], s["gamt"])
        session.commit()
        bot.send_message(msg.chat.id, f"✅ Bought {item} x{s['gamt']}!")
    else:
        bot.send_message(msg.chat.id, f"❌ You need {s['amt']} {s['price']}")

@bot.message_handler(commands=['trade'])
@safe_session
def trade(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 2:
        return bot.send_message(msg.chat.id, "❌ Use: /trade 1\n/trade 2\n/trade 3\n/trade 4")
    
    try:
        trade_num = int(args[1])
    except:
        return bot.send_message(msg.chat.id, "❌ Invalid number")
    
    trades = {
        1: {"name": "Farmer", "in": "wheat", "in_amt": 5, "out": "bread", "out_amt": 3},
        2: {"name": "Blacksmith", "in": "iron_ore", "in_amt": 3, "out": "iron_sword", "out_amt": 1},
        3: {"name": "Hunter", "in": "feather", "in_amt": 8, "out": "bow", "out_amt": 1},
        4: {"name": "Merchant", "in": "diamond", "in_amt": 2, "out": "golden_apple", "out_amt": 1},
    }
    
    if trade_num not in trades:
        return bot.send_message(msg.chat.id, "❌ Invalid number (1-4)")
    
    t = trades[trade_num]
    if p.has_item(t["in"], t["in_amt"]):
        p.remove_item(t["in"], t["in_amt"])
        p.add_item(t["out"], t["out_amt"])
        p.add_xp(5)
        session.commit()
        bot.send_message(msg.chat.id, f"✅ Traded with {t['name']}!\n🎁 {t['out']} x{t['out_amt']} +5XP")
    else:
        bot.send_message(msg.chat.id, f"❌ You need {t['in_amt']} {t['in']}")

# ===============================
# 18. الرجوع والتشغيل
# ===============================

@bot.message_handler(func=lambda m: m.text == "🔙 Back")
@safe_session
def go_back(msg):
    session.rollback()
    p, _ = get_player(session, msg.from_user.id)
    
    if p.in_nether:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Yes, leave", callback_data="nether_leave"),
            types.InlineKeyboardButton("❌ No, stay", callback_data="nether_stay")
        )
        bot.send_message(msg.chat.id, "🔥 You are in the Nether! Do you want to return to the Overworld?", reply_markup=kb)
        return
    
    tod = p.get_time_of_day()
    txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu(p))

@bot.callback_query_handler(func=lambda c: c.data == "nether_stay")
@safe_session
def nether_stay(call):
    session.rollback()
    p, _ = get_player(session, call.from_user.id)
    kb = nether.get_nether_menu()
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"🔥 **You are in the Nether!**\n\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20", kb)

# ===============================
# 19. رايلوي - منفذ (مُعدل)
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
# 20. تشغيل البوت (مُعدل)
# ===============================

if __name__ == "__main__":
    print("="*50)
    print("🤖 Minecraft Bot is starting...")
    print("✅ Everything is ready!")
    print("🔥 Game is fully upgraded with logic!")
    print("🐉 Dragon System: 3x stronger, 4 towers, 3 players max!")
    print("✨ Added: Ender Pearl in shop!")
    print("✨ Added: Help menu with full guide!")
    print("✨ Added: Full 36-slot delete system!")
    print("✨ All resources are in English!")
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
