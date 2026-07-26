import os
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

Base = declarative_base()

class Player(Base):
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True)
    username = Column(String)
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
    inventory = Column(JSON, default=lambda: {f"slot_{i}": None for i in range(36)})
    
    # Equipment (JSON)
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
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def can_sleep(self):
        return datetime.utcnow() - self.last_sleep > timedelta(hours=12)
    
    def add_xp(self, amount):
        self.xp += amount
        while self.xp >= self.level * 10:
            self.xp -= self.level * 10
            self.level += 1
            self.max_health += 1
            self.current_health = self.max_health
            if self.level % 5 == 0:
                self.skill_points += 1
            
            # فتح وصفات جديدة كل 5 مستويات
            if self.level % 5 == 0 and self.level <= 25:
                level_num = self.level // 5 + 1
                if level_num <= 5:
                    self.recipes_unlocked.append(f"level_{level_num}")
        
        # تحديث اللقب
        titles_map = {10: "مبتدئ", 20: "مستكشف", 30: "محارب", 
                     40: "صياد", 50: "بناء", 60: "ساحر", 
                     70: "بطل", 80: "أسطورة"}
        for lvl, title in titles_map.items():
            if self.level >= lvl and title not in self.titles:
                self.titles.append(title)

class WorldEvent(Base):
    __tablename__ = 'world_events'
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    active = Column(Boolean, default=True)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///minecraft_bot.db')
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
