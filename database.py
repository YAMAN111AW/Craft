import os, json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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
    
    # المخزون والمعدات
    inventory = Column(JSON, default=lambda: {f"slot_{i}": None for i in range(36)})
    equipment = Column(JSON, default=lambda: {
        "helmet": None, "chestplate": None, "leggings": None, 
        "boots": None, "weapon": None, "shield": None
    })
    
    # الحالة والموقع
    current_area = Column(String, default="forest")
    last_action = Column(DateTime, default=datetime.utcnow)
    last_sleep = Column(DateTime, default=datetime.utcnow)
    status_effects = Column(JSON, default=list)
    is_exploring = Column(Boolean, default=False)
    explore_end_time = Column(DateTime, default=None)
    
    # الإنجازات
    titles = Column(JSON, default=list)
    recipes_unlocked = Column(JSON, default=lambda: ["level_1"])
    defeated_ender_dragon = Column(Boolean, default=False)
    
    # حيوان أليف
    pet = Column(String, default=None)
    
    # وقت اللعبة
    game_time = Column(Integer, default=0)
    
    # تاريخ الإنشاء
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # ===== دوال مساعدة =====
    def get_inv(self):
        """جلب المخزون مع التأكد من صحته"""
        if self.inventory is None:
            self.inventory = {f"slot_{i}": None for i in range(36)}
            return self.inventory
        
        if isinstance(self.inventory, str):
            try:
                return json.loads(self.inventory)
            except:
                return {f"slot_{i}": None for i in range(36)}
        
        # التأكد من وجود كل الخانات
        for i in range(36):
            key = f"slot_{i}"
            if key not in self.inventory:
                self.inventory[key] = None
        
        return self.inventory
    
    def save_inv(self, inv):
        """حفظ المخزون"""
        self.inventory = inv
    
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
        """إضافة عنصر للمخزون - مع حفظ تلقائي"""
        inv = self.get_inv()
        remaining = amount
        
        # 1. نجمع مع العناصر الموجودة
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
        
        # 2. نضيف في خانات فارغة
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
        """حذف عنصر من المخزون"""
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
    
    def get_time_emoji(self):
        if self.game_time < 20:
            return "🌅"
        elif self.game_time < 60:
            return "☀️"
        elif self.game_time < 120:
            return "🌤️"
        elif self.game_time < 140:
            return "🌅"
        elif self.game_time < 180:
            return "🌆"
        else:
            return "🌙"
    
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
