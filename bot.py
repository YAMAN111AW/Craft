import os, json, random, telebot
from telebot import types
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# ===============================
# 1. قاعدة البيانات
# ===============================

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, default="Player")
    
    # المستوى والخبرة
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    skill_points = Column(Integer, default=0)
    
    # الصحة والجوع
    max_health = Column(Integer, default=20)
    current_health = Column(Integer, default=20)
    max_hunger = Column(Integer, default=20)
    current_hunger = Column(Integer, default=20)
    
    # المهارات
    strength = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    endurance = Column(Integer, default=0)
    luck = Column(Integer, default=0)
    
    # المخزون
    inventory = Column(Text, default=lambda: json.dumps({f"slot_{i}": None for i in range(36)}))
    equipment = Column(JSON, default=lambda: {
        "helmet": None, "chestplate": None, "leggings": None, 
        "boots": None, "weapon": None, "shield": None
    })
    
    # الحالة
    current_area = Column(String, default="forest")
    last_action = Column(DateTime, default=datetime.utcnow)
    last_sleep = Column(DateTime, default=datetime.utcnow)
    status_effects = Column(JSON, default=list)
    is_exploring = Column(Boolean, default=False)
    explore_end_time = Column(DateTime, default=None)
    
    # إنجازات
    titles = Column(JSON, default=list)
    recipes_unlocked = Column(JSON, default=lambda: ["level_1"])
    defeated_ender_dragon = Column(Boolean, default=False)
    
    # حيوان أليف
    pet = Column(String, default=None)
    
    # وقت اللعبة
    game_time = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ===== دوال المخزون =====
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
    
    def count_item(self, item_name):
        inv = self.get_inv()
        total = 0
        for slot in inv.values():
            if slot and slot.get("name") == item_name:
                total += slot.get("amount", 0)
        return total
    
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
            lvl = self.level // 5 + 1
            key = f"level_{lvl}"
            if lvl <= 5 and key not in recipes:
                recipes.append(key)
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
            {"name": "شجرة بلوط", "emoji": "🌳", "blocks": 6, "resources": [("oak_wood", 1)], "rare": ("apple", 1, 0.3)},
            {"name": "شجرة تنوب", "emoji": "🌲", "blocks": 6, "resources": [("spruce_wood", 1)], "rare": ("mushroom", 1, 0.3)},
            {"name": "شجرة بتولا", "emoji": "🪵", "blocks": 6, "resources": [("birch_wood", 1)], "rare": ("sap", 1, 0.25)},
            {"name": "شجرة استوائية", "emoji": "🌴", "blocks": 6, "resources": [("jungle_wood", 1)], "rare": ("tropical_fruit", 1, 0.2)},
        ]
    
    @staticmethod
    def get_rocks():
        return [
            {"name": "حجر عادي", "emoji": "🪨", "blocks": 4, "resources": [("stone", 1)]},
            {"name": "حجر فحم", "emoji": "🖤", "blocks": 4, "resources": [("stone", 1), ("coal", 1)]},
            {"name": "حجر حديد", "emoji": "⛏️", "blocks": 4, "resources": [("stone", 1), ("iron_ore", 1)]},
            {"name": "حجر ذهب", "emoji": "✨", "blocks": 4, "resources": [("stone", 1), ("gold_ore", 1)], "rare": ("diamond", 1, 0.05)},
            {"name": "حجر ألماس", "emoji": "💎", "blocks": 4, "resources": [("stone", 1), ("diamond", 1)], "rare": ("emerald", 1, 0.03)},
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
                {"name": "زومبي", "emoji": "🧟", "hp": 12, "damage": 4, "xp": 10, "drops": [("rotten_flesh", 2, 0.6)]},
                {"name": "سكلتون", "emoji": "💀", "hp": 14, "damage": 5, "xp": 12, "drops": [("bone", 3, 0.7), ("arrow", 3, 0.5)]},
                {"name": "كريبر", "emoji": "💚", "hp": 18, "damage": 10, "xp": 18, "drops": [("gunpowder", 3, 0.8)], "special": "explode"},
                {"name": "زومبي حديدي", "emoji": "🧟‍♂️", "hp": 20, "damage": 6, "xp": 15, "drops": [("iron_ore", 2, 0.4)]},
                {"name": "غول", "emoji": "👹", "hp": 28, "damage": 12, "xp": 25, "drops": [("gold_ore", 3, 0.5), ("diamond", 1, 0.15)]},
            ]
        else:
            return [
                {"name": "ذئب", "emoji": "🐺", "hp": 8, "damage": 3, "xp": 5, "drops": [("bone", 2, 0.5)], "special": "tameable"},
                {"name": "دب", "emoji": "🐻", "hp": 20, "damage": 7, "xp": 15, "drops": [("bear_meat", 2, 0.8), ("bear_pelt", 1, 0.4)]},
                {"name": "عنكبوت", "emoji": "🕷️", "hp": 8, "damage": 2, "xp": 6, "drops": [("spider_silk", 2, 0.5), ("spider_eye", 1, 0.3)]},
            ]
    
    @staticmethod
    def get_random_event(is_night):
        if is_night:
            events = [
                {"type": "loot", "msg": "🌙 وجدت صندوقاً في الظلام!", "item": random.choice(["iron_ore", "gold_ore", "diamond"]), "amount": 2},
                {"type": "loot", "msg": "🕯️ شعلة مشتعلة!", "item": "torch", "amount": 4},
            ]
        else:
            events = [
                {"type": "loot", "msg": "🎁 وجدت هدية على الأرض!", "item": random.choice(["apple", "bread", "coal"]), "amount": 2},
                {"type": "loot", "msg": "🍯 خلية نحل!", "item": "honey", "amount": 3},
            ]
        return random.choice(events) if random.random() < 0.2 else None


# ===============================
# 4. نظام التصنيع
# ===============================

class CraftingSystem:
    RECIPES = {
        "level_1": [
            {"name": "ألواح خشب", "emoji": "🪵", "in": {"oak_wood": 1}, "out": {"wooden_planks": 4}, "xp": 1},
            {"name": "عصي", "emoji": "🥢", "in": {"wooden_planks": 2}, "out": {"sticks": 4}, "xp": 1},
            {"name": "طاولة تصنيع", "emoji": "🔨", "in": {"wooden_planks": 4}, "out": {"crafting_table": 1}, "xp": 2},
            {"name": "فرن", "emoji": "🔥", "in": {"stone": 8}, "out": {"furnace": 1}, "xp": 2},
            {"name": "سياج", "emoji": "🚧", "in": {"sticks": 6}, "out": {"fence": 3}, "xp": 1},
            {"name": "باب خشبي", "emoji": "🚪", "in": {"wooden_planks": 6}, "out": {"wooden_door": 1}, "xp": 2},
        ],
        "level_2": [
            {"name": "فأس خشبي", "emoji": "🪓", "in": {"wooden_planks": 3, "sticks": 2}, "out": {"wooden_axe": 1}, "xp": 3},
            {"name": "سيف خشبي", "emoji": "🗡️", "in": {"wooden_planks": 2, "sticks": 1}, "out": {"wooden_sword": 1}, "xp": 3},
            {"name": "خبز", "emoji": "🍞", "in": {"wheat": 3}, "out": {"bread": 1}, "xp": 2},
        ],
        "level_3": [
            {"name": "فأس حجري", "emoji": "🪓", "in": {"stone": 3, "sticks": 2}, "out": {"stone_axe": 1}, "xp": 5},
            {"name": "سيف حجري", "emoji": "🗡️", "in": {"stone": 2, "sticks": 1}, "out": {"stone_sword": 1}, "xp": 5},
            {"name": "معول حديدي", "emoji": "⛏️", "in": {"iron_ore": 3, "sticks": 2}, "out": {"iron_pickaxe": 1}, "xp": 7},
            {"name": "درع حديدي", "emoji": "🛡️", "in": {"iron_ore": 8}, "out": {"iron_chestplate": 1}, "xp": 8},
        ],
        "level_4": [
            {"name": "سيف حديدي", "emoji": "🗡️", "in": {"iron_ore": 2, "sticks": 1}, "out": {"iron_sword": 1}, "xp": 8},
            {"name": "فأس ألماسي", "emoji": "🪓", "in": {"diamond": 3, "sticks": 2}, "out": {"diamond_axe": 1}, "xp": 12},
            {"name": "جرعة شفاء", "emoji": "🧪", "in": {"sap": 2, "mushroom": 1}, "out": {"healing_potion": 1}, "xp": 8},
        ],
        "level_5": [
            {"name": "سيف ألماسي", "emoji": "🗡️", "in": {"diamond": 2, "sticks": 1}, "out": {"diamond_sword": 1}, "xp": 15},
            {"name": "درع ناري", "emoji": "🔥", "in": {"fiery_coal": 5, "iron_ore": 8}, "out": {"fire_chestplate": 1}, "xp": 18},
            {"name": "عين الإندر", "emoji": "👁️", "in": {"ender_pearl": 1, "blaze_rod": 1}, "out": {"eye_of_ender": 1}, "xp": 10},
            {"name": "جناح طيران", "emoji": "🪽", "in": {"diamond": 1, "feather": 10}, "out": {"elytra": 1}, "xp": 25},
        ]
    }
    
    @classmethod
    def get_recipes(cls, player):
        all_recipes = []
        recipes = player.recipes_unlocked
        if isinstance(recipes, str):
            recipes = json.loads(recipes)
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
    
    def chop_block(self, player, tree):
        # نحاكي تكسير شجرة
        rewards = []
        for res, amt in tree["resources"]:
            player.add_item(res, amt)
            rewards.append(f"{res} x{amt}")
        
        if tree.get("rare"):
            rare_res, rare_amt, prob = tree["rare"]
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"✨ {rare_res} x{rare_amt}")
        
        hunger_cost = 0.8 if player.is_night() else 0.5
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 2)
        
        xp_reward = 2 if player.is_night() else 1
        player.add_xp(xp_reward)
        self.session.commit()
        
        return {
            "rewards": rewards,
            "hunger": player.current_hunger,
            "health": player.current_health,
            "xp": xp_reward
        }
    
    def mine_block(self, player, rock):
        rewards = []
        for res, amt in rock["resources"]:
            player.add_item(res, amt)
            rewards.append(f"{res} x{amt}")
        
        if rock.get("rare"):
            rare_res, rare_amt, prob = rock["rare"]
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"💎 {rare_res} x{rare_amt}")
        
        hunger_cost = 0.8 if player.is_night() else 0.5
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 2)
        
        xp_reward = 2 if player.is_night() else 1
        player.add_xp(xp_reward)
        self.session.commit()
        
        return {
            "rewards": rewards,
            "hunger": player.current_hunger,
            "health": player.current_health,
            "xp": xp_reward
        }
    
    def hunt_animal(self, player, animal_name):
        loot = WorldData.get_animals().get(animal_name)
        if not loot:
            return {"error": "حيوان غير معروف"}
        
        rewards = []
        for res, amt in loot:
            bonus = random.randint(0, 1) if not player.is_night() else 0
            player.add_item(res, amt + bonus)
            rewards.append(f"{res} x{amt + bonus}")
        
        hunger_cost = 1.5 if player.is_night() else 1
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        xp_reward = 5 if player.is_night() else 3
        player.add_xp(xp_reward)
        self.session.commit()
        
        return {"animal": animal_name, "rewards": rewards}
    
    def calc_damage(self, player):
        dmg = 2
        eq = player.get_equip()
        w = eq.get("weapon")
        weapon_dmg = {
            "wooden_sword": 4, "stone_sword": 6,
            "iron_sword": 8, "diamond_sword": 10
        }
        if w in weapon_dmg:
            dmg += weapon_dmg[w]
        if player.pet == "wolf":
            dmg += 3
        if player.is_night():
            dmg = int(dmg * 0.9)
        return dmg + int(dmg * player.strength * 0.02)
    
    def calc_defense(self, player):
        defense = 0
        eq = player.get_equip()
        for slot in ["helmet", "chestplate", "leggings", "boots"]:
            armor = eq.get(slot)
            if armor:
                if "diamond" in str(armor): defense += 3
                elif "iron" in str(armor): defense += 2
                elif "fire" in str(armor): defense += 4
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
            "honey": 6, "golden_apple": 4, "milk": 3, "egg": 1,
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
            player.current_health = min(player.max_health, player.current_health + 4)
        if "raw" in food and random.random() < 0.3:
            effects.append("⚠️ تسمم غذائي")
            player.current_health = max(0, player.current_health - 2)
        
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
            'wooden_sword': 4, 'stone_sword': 6,
            'iron_sword': 8, 'diamond_sword': 10
        }
        base_damage += weapon_damage.get(weapon, 1)
        
        if battle_data['is_night']:
            base_damage = int(base_damage * 0.8)
        
        if random.random() < 0.15 + (player.luck / 100):
            base_damage *= 2
            battle_data['log'].append("💥 ضربة حاسمة!")
        
        final_damage = max(1, base_damage - random.randint(0, 2))
        enemy_hp = max(0, enemy_hp - final_damage)
        
        battle_data['enemy_hp'] = enemy_hp
        battle_data['log'].append(f"🗡️ ضربت {enemy['name']} بـ {final_damage} ضرر")
        battle_data['player_defending'] = False
        
        return battle_data
    
    def player_defend(self, player, battle_data):
        shield = 3 if not battle_data['is_night'] else 2
        battle_data['player_defending'] = True
        battle_data['log'].append(f"🛡️ استعديت للدفاع (+{shield} درع)")
        return battle_data
    
    def enemy_turn(self, player, battle_data):
        enemy = battle_data['enemy']
        player_hp = battle_data['player_hp']
        
        player_defense = 5 if battle_data['player_defending'] else 0
        if battle_data['is_night']:
            player_defense = int(player_defense * 0.7)
        battle_data['player_defending'] = False
        
        enemy_damage = enemy['damage']
        if battle_data['is_night']:
            enemy_damage = int(enemy_damage * 1.3)
        
        if enemy.get('special') == 'explode' and random.random() < 0.3:
            enemy_damage *= 2
            battle_data['log'].append(f"💥 {enemy['name']} انفجر!")
        
        final_damage = max(0, enemy_damage - player_defense)
        
        if final_damage > 0:
            player_hp = max(0, player_hp - final_damage)
            battle_data['log'].append(f"💢 {enemy['name']} ضربك بـ {final_damage} ضرر")
        else:
            battle_data['log'].append(f"🛡️ تصدت هجوم {enemy['name']}!")
        
        battle_data['player_hp'] = player_hp
        
        if enemy.get('special') == 'tameable' and random.random() < 0.15 and enemy['hp'] < 5:
            battle_data['log'].append("🐺 تم ترويض الذئب!")
            player.pet = 'wolf'
            self.session.commit()
        
        return battle_data
    
    def try_escape(self, player, battle_data):
        chance = 40 + player.speed
        if battle_data['is_night']:
            chance = int(chance * 0.7)
        chance = min(90, chance)
        
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
# 7. البوت
# ===============================

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
session = Session()
gm = GameMechanics(session)
battle_system = BattleSystem(session)

# جلسات العمل
chop_sessions = {}
mine_sessions = {}
battle_sessions = {}

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🌳 الغابة", "🕳️ الكهف")
    kb.add("🏘️ القرية", "🏛️ المعبد")
    kb.add("🎒 مخزوني", "🛠️ التصنيع")
    kb.add("🍖 أكل", "🗑️ حذف")
    kb.add("❤️ حالتي", "📊 مهاراتي")
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
    event = WorldData.get_random_event(player.is_night())
    if event:
        if event['type'] == 'loot':
            player.add_item(event['item'], event['amount'])
            session.commit()
            return time_of_day, event['msg']
    return time_of_day, None


# ===== الأوامر =====@bot.message_handler(commands=['start'])
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
    
    time_of_day, event = update_time_and_events(p)
    is_night = p.is_night()
    
    txt = f"{'🌳 الغابة' if is_forest else '🕳️ الكهف'} | 🕐 {time_of_day}\n\n"
    if event:
        txt += f"✨ {event}\n\n"
    
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


# ===== تقطيع الأشجار =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("chop_"))
def start_chop(call):
    tree_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 لا يمكنك قطع الأشجار في الليل!")
    
    trees = WorldData.get_trees()
    tree = next((t for t in trees if t['name'] == tree_name), None)
    if not tree:
        return bot.answer_callback_query(call.id, "❌ شجرة غير موجودة")
    
    chop_sessions[call.from_user.id] = {"tree": tree, "blocks": tree['blocks']}
    
    txt = f"🪓 {tree['name']}\nمتبقي: {tree['blocks']} مكعبات\n\nاضغط اكسر!"
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
    data["blocks"] -= 1
    
    result = gm.chop_block(p, tree)
    session.commit()
    
    if result.get("dead"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت!")
        del chop_sessions[call.from_user.id]
        return
    
    if data["blocks"] <= 0:
        txt = f"✅ انكسرت {tree['name']}!\n\n🎁 {', '.join(result['rewards'])}\n⭐ +{result['xp']}XP"
        del chop_sessions[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
    else:
        txt = f"🪓 {tree['name']}\nمتبقي: {data['blocks']} مكعبات\n\n🎁 {', '.join(result['rewards'])}\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20\n⭐ +{result['xp']}XP"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)


# ===== تكسير الحجارة =====

@bot.callback_query_handler(func=lambda c: c.data.startswith("mine_"))
def start_mine(call):
    rock_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    rocks = WorldData.get_rocks()
    rock = next((r for r in rocks if r['name'] == rock_name), None)
    if not rock:
        return bot.answer_callback_query(call.id, "❌ حجر غير موجود")
    
    mine_sessions[call.from_user.id] = {"rock": rock, "blocks": rock['blocks']}
    
    txt = f"⛏️ {rock['name']}\nمتبقي: {rock['blocks']} مكعبات\n\nاضغط اكسر!"
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
    data["blocks"] -= 1
    
    result = gm.mine_block(p, rock)
    session.commit()
    
    if result.get("dead"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت!")
        del mine_sessions[call.from_user.id]
        return
    
    if data["blocks"] <= 0:
        txt = f"✅ انكسر {rock['name']}!\n\n🎁 {', '.join(result['rewards'])}\n⭐ +{result['xp']}XP"
        del mine_sessions[call.from_user.id]
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
    else:
        txt = f"⛏️ {rock['name']}\nمتبقي: {data['blocks']} مكعبات\n\n🎁 {', '.join(result['rewards'])}\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20\n⭐ +{result['xp']}XP"
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
    
    time_of_day, event = update_time_and_events(p)
    is_night = p.is_night()
    
    # أحداث عشوائية
    if random.random() < 0.3:
        enemies = WorldData.get_enemies(is_night)
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
    
    # استكشاف عادي
    possible = ["apple", "bread", "coal", "iron_ore", "stone"]
    if is_night:
        possible = ["coal", "iron_ore", "gold_ore", "diamond"]
    
    item = random.choice(possible)
    amt = random.randint(1, 2 + p.luck // 10)
    if is_night:
        amt += 1
    
    p.add_item(item, amt)
    xp = 4 if is_night else 2
    p.add_xp(xp)
    session.commit()
    
    txt = f"🔍 استكشاف...\n🕐 {time_of_day}\n\n🎁 وجدت {item} x{amt}!\n⭐ +{xp}XP"
    if event:
        txt += f"\n✨ {event}"
    
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
    
    # دور العدو
    if battle_data['enemy_hp'] > 0 and battle_data['player_hp'] > 0:
        battle_data = battle_system.enemy_turn(p, battle_data)
    
    session.commit()
    
    # التحقق
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
    
    # تحديث العرض
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
        return bot.send_message(msg.chat.id, "📭 لا توجد وصفات متاحة")
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(recipes[:15]):
        kb.add(types.InlineKeyboardButton(f"{r['emoji']} {r['name']}", callback_data=f"craft_{i}"))
    
    bot.send_message(msg.chat.id, "🛠️ التصنيع", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("craft_"))
def do_craft(call):
    p, _ = get_player(session, call.from_user.id)
    idx = int(call.data.split("_")[1])
    recipes = CraftingSystem.get_recipes(p)
    
    if idx < len(recipes):
        ok, msg = CraftingSystem.craft(p, recipes[idx])
        session.commit()
        bot.answer_callback_query(call.id, msg)


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
        quests = [("الفلاح", "milk", 1, "bread", 3), ("الحداد", "iron_ore", 3, "iron_sword", 1)]
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
    edit_msg(bot, call.message.chat.id, call.message.message_id, "👋 تم التوقف")


# ===== تشغيل البوت =====

print("🤖 البوت يعمل...")
print("📁 ملف واحد فقط: bot.py")
print("✅ كل شي في مكانه")
bot.infinity_polling()
