import os
from sqlalchemy import create_engine, Column, BigInteger, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
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
    
    # Inventory & Equipment - تخزين كنص JSON
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
    
    # Pet
    pet = Column(String, default=None)  # None, "wolf"
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def get_inv(self):
        if isinstance(self.inventory, str):
            return json.loads(self.inventory)
        return self.inventory or {f"slot_{i}": None for i in range(36)}
    
    def save_inv(self, inv):
        self.inventory = inv
    
    def get_equip(self):
        if isinstance(self.equipment, str):
            return json.loads(self.equipment)
        return self.equipment or {}
    
    def save_equip(self, eq):
        self.equipment = eq
    
    def has_item(self, item_name, amount=1):
        inv = self.get_inv()
        total = sum(
            slot.get("amount", 0) 
            for slot in inv.values() 
            if slot and slot.get("name") == item_name
        )
        return total >= amount
    
    def count_item(self, item_name):
        inv = self.get_inv()
        return sum(
            slot.get("amount", 0) 
            for slot in inv.values() 
            if slot and slot.get("name") == item_name
        )
    
    def add_item(self, item_name, amount=1):
        inv = self.get_inv()
        
        # Try to stack first
        for key, slot in inv.items():
            if slot and slot.get("name") == item_name and slot.get("amount", 0) < 64:
                space = 64 - slot["amount"]
                add = min(amount, space)
                slot["amount"] += add
                amount -= add
                if amount <= 0:
                    self.save_inv(inv)
                    return True
        
        # Use empty slots
        for i in range(36):
            key = f"slot_{i}"
            if not inv.get(key):
                inv[key] = {"name": item_name, "amount": min(amount, 64)}
                self.save_inv(inv)
                return True
        
        self.save_inv(inv)
        return False
    
    def remove_item(self, item_name, amount=1):
        inv = self.get_inv()
        remaining = amount
        
        for key, slot in inv.items():
            if slot and slot.get("name") == item_name:
                if slot["amount"] <= remaining:
                    remaining -= slot["amount"]
                    inv[key] = None
                else:
                    slot["amount"] -= remaining
                    remaining = 0
                if remaining <= 0:
                    self.save_inv(inv)
                    return True
        
        self.save_inv(inv)
        return remaining <= 0
    
    def can_sleep(self):
        return (datetime.utcnow() - self.last_sleep).total_seconds() >= 43200
    
    def add_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * 10:
            self.xp -= self.level * 10
            self.level += 1
            self.max_health += 1
            self.current_health = self.max_health
            if self.level % 5 == 0:
                self.skill_points += 1
            
            recipes = self.recipes_unlocked if isinstance(self.recipes_unlocked, list) else json.loads(self.recipes_unlocked)
            lvl = self.level // 5 + 1
            key = f"level_{lvl}"
            if lvl <= 5 and key not in recipes:
                recipes.append(key)
                self.recipes_unlocked = recipes
        
        titles = self.titles if isinstance(self.titles, list) else json.loads(self.titles)
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
