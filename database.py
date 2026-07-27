import os
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Boolean, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, unique=True, nullable=False)  # تغيير لـ String لتوافق أفضل
    username = Column(String, default="Player")
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    skill_points = Column(Integer, default=0)
    
    # Stats
    max_health = Column(Integer, default=20)
    current_health = Column(Integer, default=20)
    max_hunger = Column(Integer, default=20)
    current_hunger = Column(Integer, default=20)
    
    # Skills (0-100)
    strength = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    endurance = Column(Integer, default=0)
    luck = Column(Integer, default=0)
    
    # Inventory (JSON)
    inventory = Column(Text, default=lambda: json.dumps({f"slot_{i}": None for i in range(36)}))
    
    # Equipment (JSON)
    equipment = Column(Text, default=lambda: json.dumps({
        "helmet": None, "chestplate": None, "leggings": None, 
        "boots": None, "weapon": None, "shield": None
    }))
    
    # Location & Status
    current_area = Column(String, default="forest")
    last_action = Column(DateTime, default=datetime.utcnow)
    last_sleep = Column(DateTime, default=datetime.utcnow)
    status_effects = Column(Text, default="[]")
    
    # Achievements
    titles = Column(Text, default="[]")
    recipes_unlocked = Column(Text, default='["level_1"]')
    defeated_ender_dragon = Column(Boolean, default=False)
    
    # Dragon fight temp data
    dragon_crystals = Column(Integer, default=6)
    dragon_sword_hits = Column(Integer, default=0)
    final_blows = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # تحويل النصوص إلى JSON عند الحاجة
        if isinstance(self.inventory, str):
            self.inventory = self.inventory
        if isinstance(self.equipment, str):
            self.equipment = self.equipment
    
    def get_inventory(self):
        """الحصول على المخزون كـ dict"""
        if isinstance(self.inventory, str):
            return json.loads(self.inventory)
        return self.inventory
    
    def set_inventory(self, inv_dict):
        """تعيين المخزون"""
        self.inventory = json.dumps(inv_dict)
    
    def get_equipment(self):
        """الحصول على المعدات"""
        if isinstance(self.equipment, str):
            return json.loads(self.equipment)
        return self.equipment
    
    def set_equipment(self, equip_dict):
        """تعيين المعدات"""
        self.equipment = json.dumps(equip_dict)
    
    def get_status_effects(self):
        """الحصول على التأثيرات"""
        if isinstance(self.status_effects, str):
            return json.loads(self.status_effects)
        return self.status_effects
    
    def set_status_effects(self, effects_list):
        """تعيين التأثيرات"""
        self.status_effects = json.dumps(effects_list)
    
    def get_titles(self):
        """الحصول على الألقاب"""
        if isinstance(self.titles, str):
            return json.loads(self.titles)
        return self.titles
    
    def set_titles(self, titles_list):
        """تعيين الألقاب"""
        self.titles = json.dumps(titles_list)
    
    def get_recipes(self):
        """الحصول على الوصفات المفتوحة"""
        if isinstance(self.recipes_unlocked, str):
            return json.loads(self.recipes_unlocked)
        return self.recipes_unlocked
    
    def set_recipes(self, recipes_list):
        """تعيين الوصفات"""
        self.recipes_unlocked = json.dumps(recipes_list)
    
    def has_item(self, item_name, amount=1):
        """التحقق من وجود عنصر في المخزون"""
        inv = self.get_inventory()
        total = 0
        for slot, item_data in inv.items():
            if item_data and item_data.get("name") == item_name:
                total += item_data.get("amount", 0)
        return total >= amount
    
    def add_item(self, item_name, amount=1):
        """إضافة عنصر للمخزون"""
        inv = self.get_inventory()
        
        # البحث عن خانة بها نفس العنصر
        for slot in range(36):
            slot_key = f"slot_{slot}"
            item_data = inv.get(slot_key)
            
            if item_data and item_data.get("name") == item_name:
                current_amount = item_data.get("amount", 0)
                if current_amount < 64:
                    space = 64 - current_amount
                    add_amount = min(amount, space)
                    item_data["amount"] = current_amount + add_amount
                    amount -= add_amount
                    if amount <= 0:
                        self.set_inventory(inv)
                        return True
        
        # البحث عن خانة فارغة
        if amount > 0:
            for slot in range(36):
                slot_key = f"slot_{slot}"
                if inv.get(slot_key) is None:
                    inv[slot_key] = {"name": item_name, "amount": min(amount, 64)}
                    self.set_inventory(inv)
                    return True
        
        self.set_inventory(inv)
        return False
    
    def remove_item(self, item_name, amount=1):
        """إزالة عنصر من المخزون"""
        inv = self.get_inventory()
        remaining = amount
        
        for slot in range(36):
            slot_key = f"slot_{slot}"
            item_data = inv.get(slot_key)
            
            if item_data and item_data.get("name") == item_name:
                current = item_data.get("amount", 0)
                if current <= remaining:
                    inv[slot_key] = None
                    remaining -= current
                else:
                    item_data["amount"] = current - remaining
                    remaining = 0
                
                if remaining <= 0:
                    self.set_inventory(inv)
                    return True
        
        self.set_inventory(inv)
        return False
    
    def can_sleep(self):
        """التحقق من إمكانية النوم"""
        time_diff = datetime.utcnow() - self.last_sleep
        return time_diff.total_seconds() >= 43200  # 12 ساعة
    
    def add_xp(self, amount):
        """إضافة خبرة وتحديث المستوى"""
        self.xp += amount
        
        while self.xp >= self.level * 10:
            self.xp -= self.level * 10
            self.level += 1
            self.max_health += 1
            self.current_health = self.max_health
            
            if self.level % 5 == 0:
                self.skill_points += 1
            
            # فتح وصفات جديدة
            recipes = self.get_recipes()
            level_num = self.level // 5 + 1
            level_key = f"level_{level_num}"
            if level_num <= 5 and level_key not in recipes:
                recipes.append(level_key)
                self.set_recipes(recipes)
        
        # تحديث الألقاب
        titles = self.get_titles()
        titles_map = {
            10: "مبتدئ", 20: "مستكشف", 30: "محارب", 
            40: "صياد", 50: "بناء", 60: "ساحر", 
            70: "بطل", 80: "أسطورة"
        }
        
        for lvl, title in titles_map.items():
            if self.level >= lvl and title not in titles:
                titles.append(title)
        
        self.set_titles(titles)

class WorldEvent(Base):
    __tablename__ = 'world_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    active = Column(Boolean, default=True)

# إعداد قاعدة البيانات
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///minecraft_bot.db')

# تصحيح رابط PostgreSQL إذا لزم الأمر
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

# إنشاء الجداول
Base.metadata.create_all(engine)

# إنشاء جلسة
Session = sessionmaker(bind=engine)

def get_or_create_player(session, user_id, username=None):
    """الحصول على لاعب أو إنشائه"""
    try:
        player = session.query(Player).filter_by(user_id=str(user_id)).first()
        
        if not player:
            player = Player(
                user_id=str(user_id),
                username=username or f"Player_{user_id}"
            )
            session.add(player)
            session.commit()
            session.refresh(player)
        
        return player, False  # False يعني أنه موجود مسبقاً
    except Exception as e:
        session.rollback()
        # محاولة إنشاء الجداول مرة أخرى
        Base.metadata.create_all(engine)
        
        player = Player(
            user_id=str(user_id),
            username=username or f"Player_{user_id}"
        )
        session.add(player)
        session.commit()
        session.refresh(player)
        return player, True  # True يعني أنه تم إنشاؤه جديداً
