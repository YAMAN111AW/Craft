import os, json, random, telebot, logging, time
from telebot import types
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from threading import Thread

# ===============================
# 0. نظام البناء (مستورد)
# ===============================

class BuildingSystem:
    """نظام بناء البيوت في ماينكرافت"""
    
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
            "name": "🏠 بيت خشبي",
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
            "name": "🏰 بيت حجري",
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
            "name": "🏛️ قصر فاخر",
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
        return {
            "house_type": progress["house_type"],
            "house_name": self.HOUSE_TYPES[progress["house_type"]]["name"],
            "current_stage": current_stage,
            "stage_name": stage_info["name"],
            "progress": min(100, int((time_passed / time_needed) * 100)),
            "time_left": max(0, int(time_needed - time_passed)),
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
    equipment = Column(JSON, default=lambda: {
        "helmet": None, "chestplate": None, "leggings": None, 
        "boots": None, "weapon": None, "shield": None
    })
    
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
        if isinstance(self.equipment, str):
            return json.loads(self.equipment)
        return self.equipment or {}
    
    def save_equip(self, eq):
        self.equipment = eq
    
    def has_item(self, item_name, amount=1):
        inv = self.get_inv()
        total = 0
        for slot in inv.values():
            if slot and slot.get("name") == item_name:
                total += slot.get("amount", 0)
        return total >= amount
    
    def add_item(self, item_name, amount=1):
        inv = self.get_inv()
        remaining = amount
        for key, slot in inv.items():
            if slot and slot.get("name") == item_name:
                current = slot.get("amount", 0)
                if current < 64:
                    space = 64 - current
                    add = min(remaining, space)
                    slot["amount"] = current + add
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
                    slot["amount"] = current - remaining
                    remaining = 0
                if remaining <= 0:
                    self.save_inv(inv)
                    return True
        self.save_inv(inv)
        return remaining <= 0
    
    def delete_slot(self, slot_num):
        inv = self.get_inv()
        key = f"slot_{slot_num}"
        inv[key] = None
        self.save_inv(inv)
    
    def can_sleep(self):
        return (datetime.utcnow() - self.last_sleep).total_seconds() >= 43200
    
    def advance_time(self, minutes=5):
        self.game_time = (self.game_time + minutes) % 240
        return self.get_time_of_day()
    
    def get_time_of_day(self):
        if self.game_time < 20: return "🌅 الفجر"
        elif self.game_time < 60: return "☀️ الصباح"
        elif self.game_time < 120: return "🌤️ الظهيرة"
        elif self.game_time < 140: return "🌅 الغروب"
        elif self.game_time < 180: return "🌆 المساء"
        else: return "🌙 الليل"
    
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
            recipes = self.recipes_unlocked
            if isinstance(recipes, str):
                recipes = json.loads(recipes)
            if self.level >= 2 and "level_2" not in recipes:
                recipes.append("level_2")
            if self.level >= 5 and "level_3" not in recipes:
                recipes.append("level_3")
            if self.level >= 10 and "level_4" not in recipes:
                recipes.append("level_4")
            if self.level >= 15 and "level_5" not in recipes:
                recipes.append("level_5")
            self.recipes_unlocked = recipes
        titles = self.titles
        if isinstance(titles, str):
            titles = json.loads(titles)
        titles_map = {10:"مبتدئ",20:"مستكشف",30:"محارب",40:"صياد",50:"بناء",60:"ساحر",70:"بطل",80:"أسطورة"}
        for lvl, t in titles_map.items():
            if self.level >= lvl and t not in titles:
                titles.append(t)
        self.titles = titles

# ===============================
# 2. إعداد قاعدة البيانات
# ===============================

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///mc.db')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_player(session, user_id, username=None):
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
            {"name": "شجرة بلوط", "emoji": "🌳", "blocks": 8, "resources": [("oak_wood", 1)], "rare": ("apple", 1, 0.2)},
            {"name": "شجرة تنوب", "emoji": "🌲", "blocks": 10, "resources": [("spruce_wood", 1)], "rare": ("mushroom", 1, 0.2)},
            {"name": "شجرة بتولا", "emoji": "🪵", "blocks": 7, "resources": [("birch_wood", 1)], "rare": ("sap", 1, 0.15)},
            {"name": "شجرة استوائية", "emoji": "🌴", "blocks": 12, "resources": [("jungle_wood", 1)], "rare": ("tropical_fruit", 1, 0.1)},
        ]
    
    @staticmethod
    def get_rocks():
        return [
            {"name": "حجر عادي", "emoji": "🪨", "blocks": 6, "resources": [("stone", 1)]},
            {"name": "حجر فحم", "emoji": "🖤", "blocks": 8, "resources": [("stone", 1), ("coal", 1)]},
            {"name": "حجر حديد", "emoji": "⛏️", "blocks": 10, "resources": [("stone", 1), ("iron_ore", 1)]},
            {"name": "حجر ذهب", "emoji": "✨", "blocks": 12, "resources": [("stone", 1), ("gold_ore", 1)], "rare": ("diamond", 1, 0.03)},
            {"name": "حجر ألماس", "emoji": "💎", "blocks": 15, "resources": [("stone", 1), ("diamond", 1)], "rare": ("emerald", 1, 0.02)},
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
                {"type": "loot", "msg": "🌙 وجدت صندوقاً في الظلام!", "item": random.choice(["iron_ore", "gold_ore", "diamond"]), "amount": random.randint(2, 4)},
                {"type": "loot", "msg": "🕯️ شعلة مشتعلة!", "item": "torch", "amount": random.randint(4, 8)},
            ]
        else:
            events = [
                {"type": "loot", "msg": "🎁 وجدت هدية على الأرض!", "item": random.choice(["apple", "bread", "coal"]), "amount": random.randint(2, 4)},
                {"type": "loot", "msg": "🍯 خلية نحل!", "item": "honey", "amount": random.randint(3, 6)},
            ]
        return random.choice(events) if random.random() < 0.25 else None

# ===============================
# 4. نظام التصنيع
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
        ],
        "level_3": [
            {"name": "فأس حجري", "emoji": "🪓", "in": {"stone": 3, "sticks": 2}, "out": {"stone_axe": 1}, "xp": 5},
            {"name": "سيف حجري", "emoji": "🗡️", "in": {"stone": 2, "sticks": 1}, "out": {"stone_sword": 1}, "xp": 5},
            {"name": "معول حديدي", "emoji": "⛏️", "in": {"iron_ore": 3, "sticks": 2}, "out": {"iron_pickaxe": 1}, "xp": 7},
            {"name": "درع حديدي", "emoji": "🛡️", "in": {"iron_ore": 8}, "out": {"iron_chestplate": 1}, "xp": 8},
            {"name": "خبز", "emoji": "🍞", "in": {"wheat": 3}, "out": {"bread": 1}, "xp": 2},
        ],
        "level_4": [
            {"name": "سيف حديدي", "emoji": "🗡️", "in": {"iron_ore": 2, "sticks": 1}, "out": {"iron_sword": 1}, "xp": 8},
            {"name": "فأس ألماسي", "emoji": "🪓", "in": {"diamond": 3, "sticks": 2}, "out": {"diamond_axe": 1}, "xp": 12},
            {"name": "جرعة شفاء", "emoji": "🧪", "in": {"sap": 2, "mushroom": 1}, "out": {"healing_potion": 1}, "xp": 8},
            {"name": "قوس", "emoji": "🏹", "in": {"sticks": 3, "spider_silk": 3}, "out": {"bow": 1}, "xp": 4},
        ],
        "level_5": [
            {"name": "سيف ألماسي", "emoji": "🗡️", "in": {"diamond": 2, "sticks": 1}, "out": {"diamond_sword": 1}, "xp": 15},
            {"name": "درع ناري", "emoji": "🔥", "in": {"fiery_coal": 5, "iron_ore": 8}, "out": {"fire_chestplate": 1}, "xp": 18},
            {"name": "عين الإندر", "emoji": "👁️", "in": {"ender_pearl": 1, "blaze_rod": 1}, "out": {"eye_of_ender": 1}, "xp": 10},
            {"name": "جناح طيران", "emoji": "🪽", "in": {"diamond": 1, "feather": 10}, "out": {"elytra": 1}, "xp": 25},
            {"name": "تفاح ذهبي", "emoji": "🍎", "in": {"apple": 1, "gold_ore": 8}, "out": {"golden_apple": 1}, "xp": 15},
        ]
    }
    
    @classmethod
    def get_recipes(cls, player):
        all_recipes = []
        recipes = player.recipes_unlocked
        if isinstance(recipes, str):
            recipes = json.loads(recipes)
        if player.has_item("crafting_table"):
            if "base" not in recipes:
                recipes.append("base")
            if player.level >= 2 and "level_2" not in recipes:
                recipes.append("level_2")
        if player.has_item("furnace"):
            if "level_3" not in recipes:
                recipes.append("level_3")
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

# ===============================
# 5. نظام اللعبة
# ===============================

class GameMechanics:
    def __init__(self, session):
        self.session = session
    
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
        broken = total - left
        percentage = (total - left) / total if total > 0 else 1
        if percentage < 0.2:
            trunk = "🟩🟩🟩🟩🟩"
            leaves = "🌿🌿🌿"
        elif percentage < 0.4:
            trunk = "🟩🟩🟩🟫🟫"
            leaves = "🌿🌿"
        elif percentage < 0.6:
            trunk = "🟩🟫🟫🟫🟫"
            leaves = "🌿"
        elif percentage < 0.8:
            trunk = "🟫🟫🟫🟫🟫"
            leaves = "🍂"
        else:
            trunk = "💨💨💨💨💨"
            leaves = "💥"
        return f"\n   {leaves}\n   {trunk}\n   {'🪓' if percentage < 0.9 else '✅'}\n"
    
    def get_rock_animation(self, total, left):
        broken = total - left
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
    
    def chop_block(self, player, tree):
        # التحقق من وجود فأس
        has_axe = False
        eq = player.get_equip()
        if eq.get("weapon") in ["wooden_axe", "stone_axe", "iron_pickaxe", "diamond_axe"]:
            has_axe = True
        
        if not has_axe:
            return {
                "rewards": ["❌ تحتاج فأس لتقطيع الخشب!"],
                "hunger": player.current_hunger,
                "health": player.current_health,
                "xp": 0,
                "failed": True
            }
        
        # استخراج الموارد
        resource_multiplier = max(0.4, 1 - (player.level * 0.01))
        rewards = []
        for res, amt in tree["resources"]:
            if random.random() < 0.2:
                continue
            actual_amt = max(1, int(amt * resource_multiplier))
            player.add_item(res, actual_amt)
            rewards.append(f"{res} x{actual_amt}")
        
        if tree.get("rare"):
            rare_res, rare_amt, prob = tree["rare"]
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"✨ {rare_res} x{rare_amt}")
        
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
        
        return {
            "rewards": rewards,
            "hunger": player.current_hunger,
            "health": player.current_health,
            "xp": xp_reward,
            "failed": False
        }
    
    def mine_block(self, player, rock):
        # التحقق من وجود معول
        has_pickaxe = False
        eq = player.get_equip()
        if eq.get("weapon") in ["stone_axe", "iron_pickaxe", "diamond_axe"]:
            has_pickaxe = True
        # الفأس الخشبي ما ينفع للتعدين
        if eq.get("weapon") == "wooden_axe":
            has_pickaxe = False
        
        if not has_pickaxe:
            return {
                "rewards": ["❌ تحتاج معول لتكسير الحجر!"],
                "hunger": player.current_hunger,
                "health": player.current_health,
                "xp": 0,
                "failed": True
            }
        
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
        
        return {
            "rewards": rewards,
            "hunger": player.current_hunger,
            "health": player.current_health,
            "xp": xp_reward,
            "failed": False
        }
    
    def hunt_animal(self, player, animal_name):
        loot = WorldData.get_animals().get(animal_name)
        if not loot:
            return {"error": "حيوان غير معروف"}
        rewards = []
        for res, amt in loot:
            if random.random() < 0.2:
                continue
            bonus = random.randint(0, 1) if not player.is_night() else 0
            player.add_item(res, amt + bonus)
            rewards.append(f"{res} x{amt + bonus}")
        hunger_cost = 2 if player.is_night() else 1.5
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if random.random() < 0.15:
            player.current_health = max(0, player.current_health - 3)
            rewards.append("💔 جرحك الحيوان!")
        xp_reward = 5 if player.is_night() else 3
        player.add_xp(xp_reward)
        self.session.commit()
        return {"animal": animal_name, "rewards": rewards}
    
    def calc_damage(self, player):
        dmg = 2
        eq = player.get_equip()
        w = eq.get("weapon")
        weapon_dmg = {
            "wooden_sword": 5, "stone_sword": 8,
            "iron_sword": 12, "diamond_sword": 16
        }
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
        for slot in ["helmet", "chestplate", "leggings", "boots"]:
            armor = eq.get(slot)
            if armor:
                if "diamond" in str(armor): defense += 4
                elif "iron" in str(armor): defense += 3
                elif "fire" in str(armor): defense += 5
        if player.is_night():
            defense = int(defense * 0.8)
        return defense
    
    def respawn(self, player):
        player.current_health = player.max_health // 2
        player.current_hunger = 10
        player.current_area = "forest"
        player.is_exploring = False
        player.game_time = 0
        self.session.commit()
    
    def eat(self, player, food):
        food_db = {
            "apple": 4, "bread": 5, "cooked_beef": 8, "tropical_fruit": 8,
            "honey": 6, "golden_apple": 8, "milk": 3, "egg": 1,
            "raw_beef": 2, "raw_chicken": 1
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
            'player_hp': player.current_health,
            'player_max_hp': player.max_health,
            'enemy_hp': enemy['hp'],
            'enemy_max_hp': enemy['hp'],
            'enemy': enemy,
            'round': 0,
            'log': [f"⚔️ بدأ القتال مع {enemy['emoji']} {enemy['name']}!"],
            'player_defending': False,
            'is_night': player.is_night(),
        }
    
    def player_attack(self, player, battle_data):
        enemy = battle_data['enemy']
        enemy_hp = battle_data['enemy_hp']
        base_damage = player.strength + 2
        eq = player.get_equip()
        weapon = eq.get('weapon')
        weapon_damage = {
            'wooden_sword': 5, 'stone_sword': 8,
            'iron_sword': 12, 'diamond_sword': 16
        }
        base_damage += weapon_damage.get(weapon, 1)
        if battle_data['is_night']:
            base_damage = int(base_damage * 0.8)
        if random.random() < 0.15 + (player.luck / 100):
            base_damage *= 2
            battle_data['log'].append("💥 ضربة حاسمة!")
        enemy_defense = random.randint(0, 2)
        final_damage = max(1, base_damage - enemy_defense)
        enemy_hp = max(0, enemy_hp - final_damage)
        battle_data['enemy_hp'] = enemy_hp
        battle_data['log'].append(f"🗡️ ضربت {enemy['name']} بـ {final_damage} ضرر")
        battle_data['player_defending'] = False
        return battle_data
    
    def player_defend(self, player, battle_data):
        shield = 5 if not battle_data['is_night'] else 3
        battle_data['player_defending'] = True
        battle_data['log'].append(f"🛡️ استعديت للدفاع (+{shield} درع)")
        return battle_data
    
    def enemy_turn(self, player, battle_data):
        enemy = battle_data['enemy']
        player_hp = battle_data['player_hp']
        player_defense = 0
        if battle_data['player_defending']:
            player_defense = 5
            if battle_data['is_night']:
                player_defense = 3
            battle_data['player_defending'] = False
        enemy_damage = enemy['damage']
        if battle_data['is_night']:
            enemy_damage = int(enemy_damage * 1.3)
        if battle_data['round'] > 3:
            enemy_damage = int(enemy_damage * (1 + battle_data['round'] * 0.05))
        if enemy.get('special') == 'explode' and random.random() < 0.3:
            enemy_damage *= 2
            battle_data['log'].append(f"💥 {enemy['name']} انفجر!")
        elif enemy.get('special') == 'steal' and random.random() < 0.25:
            inv = player.get_inv()
            items = [s for s in inv.values() if s]
            if items:
                stolen = random.choice(items)
                if stolen['amount'] > 0:
                    stolen['amount'] -= 1
                    if stolen['amount'] == 0:
                        for key, val in inv.items():
                            if val == stolen:
                                inv[key] = None
                                break
                    battle_data['log'].append(f"🪲 {enemy['name']} سرق {stolen['name']}")
                    player.save_inv(inv)
                    self.session.commit()
        elif enemy.get('special') == 'tameable' and random.random() < 0.12 and enemy['hp'] < 5:
            battle_data['log'].append("🐕 يحاول اللعب معك!")
            if random.random() < 0.3:
                battle_data['log'].append("🐺 تم ترويض الذئب!")
                player.pet = 'wolf'
                self.session.commit()
                enemy_damage = 0
        final_damage = max(0, enemy_damage - player_defense)
        if final_damage > 0:
            player_hp = max(0, player_hp - final_damage)
            battle_data['log'].append(f"💢 {enemy['name']} ضربك بـ {final_damage} ضرر")
        else:
            battle_data['log'].append(f"🛡️ تصدت هجوم {enemy['name']}!")
        battle_data['player_hp'] = player_hp
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
    
    def get_random_event(self, player):
        events = []
        is_night = player.is_night()
        if is_night:
            if random.random() < 0.15:
                enemies = WorldData.get_enemies(True)
                enemy = random.choice(enemies)
                events.append({
                    'type': 'enemy',
                    'msg': f"⚠️ {enemy['emoji']} {enemy['name']} يهاجمك!",
                    'enemy': enemy
                })
        else:
            if random.random() < 0.1:
                events.append({
                    'type': 'loot',
                    'msg': "🎁 وجدت شيءاً على الأرض!",
                    'item': random.choice(['apple', 'bread', 'coal', 'iron_ore']),
                    'amount': random.randint(1, 3)
                })
        return events


# ===============================
# 7. البوت
# ===============================

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    TOKEN = "ضع_التوكن_هنا_للاختبار"

bot = telebot.TeleBot(TOKEN)
session = Session()
gm = GameMechanics(session)
battle_system = BattleSystem(session)
building_system = BuildingSystem(session)

# جلسات العمل
chop_sessions = {}
mine_sessions = {}
battle_sessions = {}
chop_timers = {}
mine_timers = {}

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🌳 الغابة", "🕳️ الكهف")
    kb.add("🏘️ القرية", "🏛️ المعبد")
    kb.add("🎒 مخزوني", "🛠️ التصنيع")
    kb.add("🏠 بناء", "🍖 أكل")
    kb.add("🗑️ حذف", "❤️ حالتي")
    kb.add("📊 مهاراتي", "🔙 رجوع")
    return kb

def edit_msg(bot, chat_id, msg_id, text, reply_markup=None):
    try:
        if reply_markup:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
        else:
            bot.edit_message_text(text, chat_id, msg_id)
        return True
    except Exception as e:
        if "message is not modified" in str(e):
            return True
        if "message to edit not found" in str(e):
            bot.send_message(chat_id, text, reply_markup=reply_markup)
        return False

def update_time_and_events(player):
    time_of_day = gm.update_game_time(player)
    events = battle_system.get_random_event(player)
    for event in events:
        if event['type'] == 'loot':
            player.add_item(event['item'], event['amount'])
            session.commit()
    return time_of_day, events

# ===== الأوامر الأساسية =====

@bot.message_handler(commands=['start'])
def start(msg):
    p, new = get_player(session, msg.from_user.id, msg.from_user.first_name)
    if new:
        txt = "🌟 أهلاً بك في عالم ماينكرافت!\n\nاستخدم الأزرار للتنقل."
    else:
        tod = p.get_time_of_day()
        txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu())

@bot.message_handler(commands=['additem'])
def add_item_cmd(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 3:
        return bot.send_message(msg.chat.id, "استخدم: /additem اسم_العنصر العدد")
    item = args[1]
    try:
        amt = int(args[2])
    except:
        return bot.send_message(msg.chat.id, "❌ العدد يجب أن يكون رقماً")
    p.add_item(item, amt)
    session.commit()
    bot.send_message(msg.chat.id, f"✅ تم إضافة {amt} من {item}!")

@bot.message_handler(commands=['debug_inv'])
def debug_inv(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    inv = p.get_inv()
    items = [s for s in inv.values() if s]
    txt = f"🔍 عدد العناصر: {len(items)}\n"
    for s in items[:10]:
        txt += f"- {s['name']} x{s['amount']}\n"
    bot.send_message(msg.chat.id, txt or "📭 المخزون فارغ")

# ===== منطقة الغابة والكهف =====

@bot.message_handler(func=lambda m: m.text in ["🌳 الغابة", "🕳️ الكهف"])
def area_menu(msg):
    is_forest = msg.text == "🌳 الغابة"
    p, _ = get_player(session, msg.from_user.id)
    time_of_day, events = update_time_and_events(p)
    is_night = p.is_night()
    
    txt = f"{'🌳 الغابة' if is_forest else '🕳️ الكهف'} | 🕐 {time_of_day}\n\n"
    for event in events:
        if event['type'] == 'enemy':
            txt += f"⚠️ {event['msg']}\n"
        elif event['type'] == 'loot':
            txt += f"✅ {event['msg']}\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if is_forest and not is_night:
        trees = WorldData.get_trees()
        for tree in random.sample(trees, min(2, len(trees))):
            txt += f"🌳 {tree['name']} ({tree['blocks']} مكعبات)\n"
            kb.add(types.InlineKeyboardButton(f"🪓 {tree['name']}", callback_data=f"chop_{tree['name']}"))
    
    if not is_forest:
        rocks = WorldData.get_rocks()
        for rock in random.sample(rocks, min(2, len(rocks))):
            txt += f"🪨 {rock['name']} ({rock['blocks']} مكعبات)\n"
            kb.add(types.InlineKeyboardButton(f"⛏️ {rock['name']}", callback_data=f"mine_{rock['name']}"))
    
    if is_forest and not is_night:
        animals = list(WorldData.get_animals().keys())
        for animal in random.sample(animals, min(2, len(animals))):
            kb.add(types.InlineKeyboardButton(f"🏹 {animal}", callback_data=f"hunt_{animal}"))
    
    kb.add(types.InlineKeyboardButton("🔍 استكشاف", callback_data=f"explore_{'forest' if is_forest else 'cave'}"))
    
    if is_night:
        txt += "\n🌙 الليل! الأعداء في كل مكان!"
    
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

# ===== تقطيع الأشجار (مع نظام الوقت) =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("chop_"))
def start_chop(call):
    tree_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 لا يمكنك قطع الأشجار في الليل!")
    
    # تحقق من وجود فأس
    eq = p.get_equip()
    if eq.get("weapon") not in ["wooden_axe", "stone_axe", "iron_pickaxe", "diamond_axe"]:
        return bot.answer_callback_query(call.id, "❌ تحتاج فأس لتقطيع الخشب!\nاصنع فأساً أولاً.")
    
    trees = WorldData.get_trees()
    tree = next((t for t in trees if t['name'] == tree_name), None)
    if not tree:
        return bot.answer_callback_query(call.id, "❌ شجرة غير موجودة")
    
    # وقت التكسير حسب الأداة
    tool_speed = {
        "wooden_axe": 3,
        "stone_axe": 2,
        "iron_pickaxe": 1.5,
        "diamond_axe": 1
    }
    weapon = eq.get("weapon")
    break_time = tool_speed.get(weapon, 4)  # افتراضي 4 ثواني
    
    chop_sessions[call.from_user.id] = {"tree": tree, "blocks": tree['blocks'], "break_time": break_time}
    
    animation = gm.get_tree_animation(tree['blocks'], tree['blocks'])
    txt = f"🪓 {tree['name']}\nمتبقي: {tree['blocks']} مكعبات\n{animation}\n\n⏳ وقت التكسير: {break_time} ثانية\n\nاضغط اكسر!"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_chop")
def do_chop(call):
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in chop_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    
    data = chop_sessions[call.from_user.id]
    tree = data["tree"]
    
    # محاكاة وقت التكسير
    break_time = data.get("break_time", 3)
    
    # إظهار رسالة انتظار
    bot.answer_callback_query(call.id, f"⏳ جارٍ التكسير... انتظر {break_time} ثانية", show_alert=True)
    
    # انتظر الوقت المطلوب
    time.sleep(break_time)
    
    data["blocks"] -= 1
    
    result = gm.chop_block(p, tree)
    session.commit()
    
    if result.get("dead"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت!")
        del chop_sessions[call.from_user.id]
        return
    
    if result.get("failed"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "❌ تحتاج فأس لتقطيع الخشب!")
        del chop_sessions[call.from_user.id]
        return
    
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

# ===== تكسير الحجارة (مع نظام الوقت) =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("mine_"))
def start_mine(call):
    rock_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    # تحقق من وجود معول
    eq = p.get_equip()
    if eq.get("weapon") not in ["stone_axe", "iron_pickaxe", "diamond_axe"]:
        return bot.answer_callback_query(call.id, "❌ تحتاج معول لتكسير الحجر!\nاصنع معولاً أولاً.")
    
    # الفأس الخشبي ما ينفع
    if eq.get("weapon") == "wooden_axe":
        return bot.answer_callback_query(call.id, "❌ الفأس الخشبي لا يكسر الحجر!\nاصنع معولاً حجرياً أو حديدياً.")
    
    rocks = WorldData.get_rocks()
    rock = next((r for r in rocks if r['name'] == rock_name), None)
    if not rock:
        return bot.answer_callback_query(call.id, "❌ حجر غير موجود")
    
    # وقت التكسير حسب الأداة
    tool_speed = {
        "stone_axe": 3,
        "iron_pickaxe": 2,
        "diamond_axe": 1.5
    }
    weapon = eq.get("weapon")
    break_time = tool_speed.get(weapon, 4)
    
    mine_sessions[call.from_user.id] = {"rock": rock, "blocks": rock['blocks'], "break_time": break_time}
    
    animation = gm.get_rock_animation(rock['blocks'], rock['blocks'])
    txt = f"⛏️ {rock['name']}\nمتبقي: {rock['blocks']} مكعبات\n{animation}\n\n⏳ وقت التكسير: {break_time} ثانية\n\nاضغط اكسر!"
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_mine")
def do_mine(call):
    p, _ = get_player(session, call.from_user.id)
    if call.from_user.id not in mine_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    
    data = mine_sessions[call.from_user.id]
    rock = data["rock"]
    
    break_time = data.get("break_time", 3)
    
    bot.answer_callback_query(call.id, f"⏳ جارٍ التكسير... انتظر {break_time} ثانية", show_alert=True)
    time.sleep(break_time)
    
    data["blocks"] -= 1
    
    result = gm.mine_block(p, rock)
    session.commit()
    
    if result.get("dead"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت!")
        del mine_sessions[call.from_user.id]
        return
    
    if result.get("failed"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "❌ تحتاج معول لتكسير الحجر!")
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

# ===== صيد الحيوانات =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("hunt_"))
def hunt(call):
    animal_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 الحيوانات نائمة في الليل!")
    
    # تحقق من وجود قوس أو سيف
    eq = p.get_equip()
    weapon = eq.get("weapon")
    if weapon not in ["bow", "wooden_sword", "stone_sword", "iron_sword", "diamond_sword"]:
        return bot.answer_callback_query(call.id, "❌ تحتاج سيف أو قوس للصيد!")
    
    result = gm.hunt_animal(p, animal_name)
    session.commit()
    
    if "error" in result:
        return bot.answer_callback_query(call.id, result["error"])
    
    txt = f"🏹 صيد {animal_name}!\n\n🎁 {', '.join(result['rewards'])}"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

# ===== استكشاف =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_"))
def explore(call):
    area = call.data.split("_")[1]
    p, _ = get_player(session, call.from_user.id)
    
    time_of_day, events = update_time_and_events(p)
    is_night = p.is_night()
    
    for event in events:
        if event['type'] == 'enemy' and 'enemy' in event:
            enemy = event['enemy']
            battle_data = battle_system.start_battle(p, enemy)
            battle_sessions[call.from_user.id] = battle_data
            
            txt = f"⚔️ هجوم!\n{enemy['emoji']} {enemy['name']} ظهر فجأة!\n🕐 {time_of_day}\n\n"
            txt += f"❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n"
            txt += f"❤️ {enemy['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
            
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"),
                types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend")
            )
            kb.add(
                types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run")
            )
            
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
            return
    
    if random.random() < 0.25:
        enemies = WorldData.get_enemies(is_night)
        if enemies:
            enemy = random.choice(enemies)
            battle_data = battle_system.start_battle(p, enemy)
            battle_sessions[call.from_user.id] = battle_data
            
            txt = f"⚔️ هجوم!\n{enemy['emoji']} {enemy['name']} ظهر فجأة!\n🕐 {time_of_day}\n\n"
            txt += f"❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n"
            txt += f"❤️ {enemy['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
            
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"),
                types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend")
            )
            kb.add(
                types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run")
            )
            
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
            return
    
    possible = ["apple", "bread", "coal", "iron_ore", "stone", "gold_ore"]
    if is_night:
        possible = ["coal", "iron_ore", "gold_ore", "diamond", "emerald"]
    
    item = random.choice(possible)
    amt = random.randint(1, 2 + p.luck // 10)
    if is_night:
        amt += 1
    
    p.add_item(item, amt)
    xp = 4 if is_night else 2
    p.add_xp(xp)
    session.commit()
    
    txt = f"🔍 استكشاف...\n🕐 {time_of_day}\n\n🎁 وجدت {item} x{amt}!\n⭐ +{xp}XP"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

# ===== القتال =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("battle_"))
def battle_action(call):
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
            txt = f"🏃 هربت!\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-3:])
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
            return
    
    if battle_data['enemy_hp'] > 0 and battle_data['player_hp'] > 0:
        battle_data = battle_system.enemy_turn(p, battle_data)
    
    session.commit()
    
    status, battle_data = battle_system.check_win(p, battle_data)
    session.commit()
    
    if status == 'win':
        del battle_sessions[call.from_user.id]
        txt = "🎉 انتصرت!\n\n" + "\n".join(battle_data['log'][-5:])
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
        return
    
    if status == 'dead':
        del battle_sessions[call.from_user.id]
        txt = "💀 لقد مت!\n\n" + "\n".join(battle_data['log'][-3:]) + "\n\nاستخدم /start"
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
        return
    
    battle_data['round'] += 1
    battle_sessions[call.from_user.id] = battle_data
    
    enemy = battle_data['enemy']
    txt = f"⚔️ الجولة {battle_data['round']}\n🕐 {time_of_day}\n\n"
    txt += "\n".join(battle_data['log'][-3:])
    txt += f"\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n"
    txt += f"❤️ {enemy['name']}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"),
        types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend")
    )
    kb.add(
        types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run")
    )
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

# ===== التصنيع =====

@bot.message_handler(func=lambda m: m.text == "🛠️ التصنيع")
def craft_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    recipes = CraftingSystem.get_recipes(p)
    
    if not recipes:
        return bot.send_message(msg.chat.id, "📭 لا توجد وصفات متاحة\n\nاصنع طاولة تصنيع أولاً!")
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(recipes[:20]):
        kb.add(types.InlineKeyboardButton(f"{r['emoji']} {r['name']}", callback_data=f"craft_{i}"))
    
    bot.send_message(msg.chat.id, f"🛠️ التصنيع\n🕐 {p.get_time_of_day()}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("craft_"))
def do_craft(call):
    p, _ = get_player(session, call.from_user.id)
    idx = int(call.data.split("_")[1])
    recipes = CraftingSystem.get_recipes(p)
    
    if idx < len(recipes):
        ok, msg = CraftingSystem.craft(p, recipes[idx])
        session.commit()
        bot.answer_callback_query(call.id, msg)

# ===== بناء البيوت =====

@bot.message_handler(func=lambda m: m.text == "🏠 بناء")
def building_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_events(p)
    
    available = building_system.get_available_houses(p)
    
    if not available:
        return bot.send_message(msg.chat.id, "❌ ليس لديك مستوى كافٍ لبناء أي بيت\n\nالمستويات المطلوبة:\n🏠 خشبي: مستوى 1\n🏰 حجري: مستوى 5\n🏛️ قصر: مستوى 15")
    
    status = building_system.get_building_status(p)
    if status:
        if status["is_complete"]:
            success, msg_text = building_system.complete_stage(p)
            if success:
                bot.send_message(msg.chat.id, msg_text)
                return
            else:
                bot.send_message(msg.chat.id, msg_text)
                return
        else:
            txt = f"🏗️ جارٍ البناء...\n"
            txt += f"البيت: {status['house_name']}\n"
            txt += f"المرحلة: {status['stage_name']}\n"
            txt += f"التقدم: {'█' * (status['progress']//10)}{'░' * (10 - status['progress']//10)} {status['progress']}%\n"
            txt += f"الوقت المتبقي: {status['time_left']} ثانية"
            
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="build_status"))
            kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="build_cancel"))
            
            bot.send_message(msg.chat.id, txt, reply_markup=kb)
            return
    
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
        txt += f"{house['emoji']} {house['name']}\n"
        txt += f"📦 الموارد: {resources_text}\n"
        txt += f"⭐ المكافآت: {house['bonus']}\n\n"
        
        kb.add(types.InlineKeyboardButton(
            f"{house['emoji']} بناء {house['name']}",
            callback_data=f"build_{house_type}"
        ))
    
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("build_"))
def start_build(call):
    house_type = call.data[6:]
    p, _ = get_player(session, call.from_user.id)
    
    success, msg = building_system.start_building(p, house_type)
    session.commit()
    
    if success:
        status = building_system.get_building_status(p)
        txt = f"{msg}\n\nالتقدم: 0%\n⏳ انتظر {status['time_left']} ثانية"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="build_status"))
        kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="build_cancel"))
        
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    else:
        bot.answer_callback_query(call.id, msg)

@bot.callback_query_handler(func=lambda c: c.data == "build_status")
def check_build_status(call):
    p, _ = get_player(session, call.from_user.id)
    status = building_system.get_building_status(p)
    
    if not status:
        return bot.answer_callback_query(call.id, "❌ لا يوجد بناء قيد التنفيذ")
    
    if status["is_complete"]:
        success, msg = building_system.complete_stage(p)
        session.commit()
        edit_msg(bot, call.message.chat.id, call.message.message_id, msg)
        return
    
    txt = f"🏗️ جارٍ البناء...\n"
    txt += f"البيت: {status['house_name']}\n"
    txt += f"المرحلة: {status['stage_name']}\n"
    txt += f"التقدم: {'█' * (status['progress']//10)}{'░' * (10 - status['progress']//10)} {status['progress']}%\n"
    txt += f"الوقت المتبقي: {status['time_left']} ثانية"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔄 تحديث", callback_data="build_status"))
    kb.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="build_cancel"))
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "build_cancel")
def cancel_build(call):
    p, _ = get_player(session, call.from_user.id)
    
    if p.user_id in building_system.building_progress:
        del building_system.building_progress[p.user_id]
        session.commit()
        edit_msg(bot, call.message.chat.id, call.message.message_id, "❌ تم إلغاء البناء")
    else:
        bot.answer_callback_query(call.id, "❌ لا يوجد بناء قيد التنفيذ")

# ===== المخزون والأكل والحالة =====

@bot.message_handler(func=lambda m: m.text == "🎒 مخزوني")
def inventory(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    
    if not items:
        return bot.send_message(msg.chat.id, f"📭 المخزون فارغ\n🕐 {p.get_time_of_day()}")
    
    txt = f"🎒 مخزونك\n🕐 {p.get_time_of_day()}\n\n"
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    
    if len(items) > 18:
        txt += f"\n... و {len(items)-18} عناصر أخرى"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "🗑️ حذف")
def delete_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    
    if not items:
        return bot.send_message(msg.chat.id, "📭 المخزون فارغ")
    
    txt = "🗑️ اختر عنصر للحذف:\n\n"
    kb = types.InlineKeyboardMarkup(row_width=3)
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
        kb.add(types.InlineKeyboardButton(f"{idx+1}", callback_data=f"del_{idx}"))
    
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_item(call):
    p, _ = get_player(session, call.from_user.id)
    slot = int(call.data.split("_")[1])
    p.delete_slot(slot)
    session.commit()
    bot.answer_callback_query(call.id, f"✅ تم حذف الخانة {slot+1}")

@bot.message_handler(func=lambda m: m.text == "🍖 أكل")
def eat_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    inv = p.get_inv()
    foods = [s for s in inv.values() if s and s['name'] in ["apple", "bread", "cooked_beef", "honey", "golden_apple", "raw_beef"]]
    
    if not foods:
        return bot.send_message(msg.chat.id, "🍖 لا طعام")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for f in foods[:10]:
        kb.add(types.InlineKeyboardButton(f"{f['name']} x{f['amount']}", callback_data=f"eat_{f['name']}"))
    
    bot.send_message(msg.chat.id, "🍖 اختر الطعام", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("eat_"))
def do_eat(call):
    p, _ = get_player(session, call.from_user.id)
    food = call.data[4:]
    res = gm.eat(p, food)
    session.commit()
    
    if "error" in res:
        bot.answer_callback_query(call.id, res["error"])
    else:
        txt = f"🍖 {food} | +{res['hunger']} شبع | {res['current']}/20"
        if res.get('effects'):
            txt += "\n" + "\n".join(res['effects'])
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.message_handler(func=lambda m: m.text == "❤️ حالتي")
def status(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    titles = p.titles if isinstance(p.titles, list) else []
    txt = f"👤 {p.username} | ⭐ Lv.{p.level}\n"
    txt += f"❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n"
    txt += f"🕐 {p.get_time_of_day()}\n"
    txt += f"🏅 {', '.join(titles) if titles else 'لا ألقاب'}\n"
    txt += f"🐺 حيوان: {p.pet or 'لا يوجد'}"
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📊 مهاراتي")
def skills(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    txt = f"⚔️ قوة: {p.strength} | 💨 سرعة: {p.speed}\n"
    txt += f"💪 تحمل: {p.endurance} | 🍀 حظ: {p.luck}\n"
    txt += f"🎯 نقاط: {p.skill_points}"
    
    if p.skill_points > 0:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("⚔️ قوة", callback_data="sk_strength"),
            types.InlineKeyboardButton("💨 سرعة", callback_data="sk_speed"),
            types.InlineKeyboardButton("💪 تحمل", callback_data="sk_endurance"),
            types.InlineKeyboardButton("🍀 حظ", callback_data="sk_luck")
        )
        bot.send_message(msg.chat.id, txt, reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, txt)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sk_"))
def upgrade_skill(call):
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

# ===== القرية =====

@bot.message_handler(func=lambda m: m.text == "🏘️ القرية")
def village(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_events(p)
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("😴 نوم", callback_data="v_sleep"),
        types.InlineKeyboardButton("📋 مهمة", callback_data="v_quest"),
        types.InlineKeyboardButton("🛒 متجر", callback_data="v_shop")
    )
    bot.send_message(msg.chat.id, f"🏘️ القرية\n🕐 {p.get_time_of_day()}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ["v_sleep", "v_quest", "v_shop"])
def village_actions(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.data == "v_sleep":
        res = gm.sleep(p)
        session.commit()
        if "error" in res:
            bot.answer_callback_query(call.id, res["error"])
        else:
            edit_msg(bot, call.message.chat.id, call.message.message_id, f"😴 {res['msg']}\n❤️ {res['hp']} | 🍖 {res['hunger']}")
    
    elif call.data == "v_quest":
        quests = [
            ("الفلاح", "milk", 1, "bread", 3),
            ("الحداد", "iron_ore", 3, "iron_sword", 1),
            ("الصياد", "feather", 5, "bow", 1),
        ]
        q = random.choice(quests)
        if p.has_item(q[1], q[2]):
            p.remove_item(q[1], q[2])
            p.add_item(q[3], q[4])
            p.add_xp(5)
            session.commit()
            bot.answer_callback_query(call.id, f"✅ {q[0]}! +{q[3]} +5XP")
        else:
            bot.answer_callback_query(call.id, f"❌ تحتاج {q[2]} {q[1]}")
    
    elif call.data == "v_shop":
        txt = "🛒 المتجر\n/buy تفاح = 2 خشب\n/buy لحم = 1 حديد"
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.message_handler(commands=['buy'])
def buy(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 2:
        return bot.send_message(msg.chat.id, "/buy تفاح أو /buy لحم")
    
    shop = {
        "تفاح": {"price": "oak_wood", "amt": 2, "give": "apple", "gamt": 3},
        "لحم": {"price": "iron_ore", "amt": 1, "give": "cooked_beef", "gamt": 1}
    }
    
    item = args[1]
    if item not in shop:
        return bot.send_message(msg.chat.id, "❌ غير متوفر")
    
    s = shop[item]
    if p.has_item(s["price"], s["amt"]):
        p.remove_item(s["price"], s["amt"])
        p.add_item(s["give"], s["gamt"])
        session.commit()
        bot.send_message(msg.chat.id, f"✅ اشتريت {item}!")
    else:
        bot.send_message(msg.chat.id, f"❌ تحتاج {s['amt']} {s['price']}")

# ===== توقف =====

@bot.callback_query_handler(func=lambda c: c.data == "stop")
def stop(call):
    uid = call.from_user.id
    chop_sessions.pop(uid, None)
    mine_sessions.pop(uid, None)
    battle_sessions.pop(uid, None)
    if uid in building_system.building_progress:
        del building_system.building_progress[uid]
    edit_msg(bot, call.message.chat.id, call.message.message_id, "👋 تم التوقف")

@bot.message_handler(func=lambda m: m.text == "🔙 رجوع")
def go_back(msg):
    p, _ = get_player(session, msg.from_user.id)
    tod = p.get_time_of_day()
    txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu())

# ===============================
# 8. رايلوي - منفذ (للحفاظ على البوت شغال)
# ===============================

def keep_alive():
    """تشغيل سيرفر بسيط عشان رايلوي ما يوقف البوت"""
    try:
        from flask import Flask
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return "🤖 Minecraft Bot is running!"
        
        @app.route('/health')
        def health():
            return "OK", 200
        
        port = int(os.environ.get('PORT', 8080))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"⚠️ Flask error: {e}")

# ===============================
# 9. تشغيل البوت
# ===============================

if __name__ == "__main__":
    print("🤖 Minecraft Bot is starting...")
    print("📁 All in one file: bot.py")
    print("✅ Everything is ready!")
    print("🔥 Game is fully upgraded with logic!")
    
    # تشغيل سيرفر Flask في خلفية
    Thread(target=keep_alive, daemon=True).start()
    
    # تشغيل البوت
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        print(f"❌ Bot error: {e}")
        time.sleep(5)
