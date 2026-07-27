# في ملف database.py، استخدم هذا الكود المتوافق:

import os
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Boolean, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)  # نحتفظ بالـ Integer القديم
    username = Column(String, default="Player")
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    skill_points = Column(Integer, default=0)
    
    # Stats
    max_health = Column(Integer, default=20)
    current_health = Column(Integer, default=20)
    max_hunger = Column(Integer, default=20)
    current_hunger = Column(Integer, default=20)
    
    # Skills
    strength = Column(Integer, default=0)
    speed = Column(Integer, default=0)
    endurance = Column(Integer, default=0)
    luck = Column(Integer, default=0)
    
    # Inventory - نستخدم JSON لكن نتعامل معه بحذر
    inventory = Column(JSON, default=lambda: {f"slot_{i}": None for i in range(36)})
    equipment = Column(JSON, default=lambda: {
        "helmet": None, "chestplate": None, "leggings": None, 
        "boots": None, "weapon": None, "shield": None
    })
    
    # Location & Status
    current_area = Column(String, default="forest")
    last_action = Column(DateTime, default=datetime.utcnow)
    last_sleep = Column(DateTime, default=datetime.utcnow)
    status_effects = Column(JSON, default=list)
    
    # Achievements
    titles = Column(JSON, default=list)
    recipes_unlocked = Column(JSON, default=lambda: ["level_1"])
    defeated_ender_dragon = Column(Boolean, default=False)
    
    # Dragon fight temp data
    dragon_crystals = Column(Integer, default=6)
    dragon_sword_hits = Column(Integer, default=0)
    final_blows = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def get_inventory(self):
        """الحصول على المخزون بشكل آمن"""
        if self.inventory is None:
            self.inventory = {f"slot_{i}": None for i in range(36)}
        if isinstance(self.inventory, str):
            try:
                return json.loads(self.inventory)
            except:
                return {f"slot_{i}": None for i in range(36)}
        return self.inventory
    
    def set_inventory(self, inv_dict):
        """تعيين المخزون"""
        self.inventory = inv_dict
    
    def get_equipment(self):
        """الحصول على المعدات"""
        if self.equipment is None:
            self.equipment = {"helmet": None, "chestplate": None, "leggings": None, 
                            "boots": None, "weapon": None, "shield": None}
        if isinstance(self.equipment, str):
            try:
                return json.loads(self.equipment)
            except:
                return {"helmet": None, "chestplate": None, "leggings": None, 
                       "boots": None, "weapon": None, "shield": None}
        return self.equipment
    
    def set_equipment(self, equip_dict):
        """تعيين المعدات"""
        self.equipment = equip_dict
    
    def get_status_effects(self):
        """الحصول على التأثيرات"""
        if self.status_effects is None:
            return []
        if isinstance(self.status_effects, str):
            try:
                return json.loads(self.status_effects)
            except:
                return []
        return self.status_effects
    
    def set_status_effects(self, effects_list):
        """تعيين التأثيرات"""
        self.status_effects = effects_list
    
    def get_titles(self):
        """الحصول على الألقاب"""
        if self.titles is None:
            return []
        if isinstance(self.titles, str):
            try:
                return json.loads(self.titles)
            except:
                return []
        return self.titles
    
    def set_titles(self, titles_list):
        """تعيين الألقاب"""
        self.titles = titles_list
    
    def get_recipes(self):
        """الحصول على الوصفات"""
        if self.recipes_unlocked is None:
            return ["level_1"]
        if isinstance(self.recipes_unlocked, str):
            try:
                return json.loads(self.recipes_unlocked)
            except:
                return ["level_1"]
        return self.recipes_unlocked
    
    def set_recipes(self, recipes_list):
        """تعيين الوصفات"""
        self.recipes_unlocked = recipes_list
    
    def has_item(self, item_name, amount=1):
        """التحقق من وجود عنصر"""
        inv = self.get_inventory()
        total = 0
        for slot, item_data in inv.items():
            if item_data and isinstance(item_data, dict) and item_data.get("name") == item_name:
                total += item_data.get("amount", 0)
        return total >= amount
    
    def add_item(self, item_name, amount=1):
        """إضافة عنصر للمخزون"""
        inv = self.get_inventory()
        
        # البحث عن خانة بها نفس العنصر
        for slot in range(36):
            slot_key = f"slot_{slot}"
            item_data = inv.get(slot_key)
            
            if item_data and isinstance(item_data, dict) and item_data.get("name") == item_name:
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
                if inv.get(slot_key) is None or inv.get(slot_key) == {}:
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
            
            if item_data and isinstance(item_data, dict) and item_data.get("name") == item_name:
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
        if self.last_sleep is None:
            return True
        time_diff = datetime.utcnow() - self.last_sleep
        return time_diff.total_seconds() >= 43200
    
    def add_xp(self, amount):
        """إضافة خبرة"""
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

# إعداد قاعدة البيانات
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///minecraft_bot.db')

if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

# إنشاء الجداول (فقط إذا لم تكن موجودة)
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

def get_or_create_player(session, user_id, username=None):
    """الحصول على لاعب أو إنشائه - متوافق مع القاعدة القديمة"""
    try:
        # البحث بـ user_id كـ Integer
        player = session.query(Player).filter_by(user_id=int(user_id)).first()
        
        if not player:
            player = Player(
                user_id=int(user_id),
                username=username or f"Player_{user_id}"
            )
            session.add(player)
            session.commit()
            return player, True
        
        return player, False
        
    except Exception as e:
        session.rollback()
        print(f"خطأ في get_or_create_player: {e}")
        
        # محاولة إنشاء اللاعب من جديد
        try:
            player = Player(
                user_id=int(user_id),
                username=username or f"Player_{user_id}"
            )
            session.add(player)
            session.commit()
            return player, True
        except Exception as e2:
            print(f"فشل إنشاء اللاعب: {e2}")
            raise
