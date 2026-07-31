import json
from datetime import datetime

class BuildingSystem:
    """نظام بناء البيوت في ماينكرافت"""
    
    # مراحل بناء البيت
    BUILDING_STAGES = {
        "foundation": {
            "name": "🏗️ الأساس",
            "emoji": "🏗️",
            "resources": {"stone": 10, "oak_wood": 5},
            "time": 30,  # ثواني
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
    
    # أنواع البيوت
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
        self.building_progress = {}  # user_id -> {house_type, current_stage, started_at}
    
    def get_available_houses(self, player):
        """يجلب أنواع البيوت المتاحة حسب مستوى اللاعب"""
        available = []
        
        if player.level >= 1:
            available.append("wooden")
        if player.level >= 5:
            available.append("stone")
        if player.level >= 15:
            available.append("mansion")
        
        return available
    
    def get_house_info(self, house_type):
        """معلومات عن نوع البيت"""
        return self.HOUSE_TYPES.get(house_type)
    
    def get_stage_info(self, stage_name):
        """معلومات عن مرحلة بناء معينة"""
        return self.BUILDING_STAGES.get(stage_name)
    
    def can_build(self, player, house_type):
        """هل يمكن البدء في بناء هذا البيت؟"""
        house = self.HOUSE_TYPES.get(house_type)
        if not house:
            return False, "❌ نوع بيت غير معروف"
        
        # تحقق من الموارد للمرحلة الأولى
        first_stage = house["stages"][0]
        resources = house["resources"].get(first_stage, {})
        
        for item, amt in resources.items():
            if not player.has_item(item, amt):
                return False, f"❌ تحتاج {amt} من {item} للمرحلة الأولى"
        
        return True, "✅ يمكن البدء بالبناء"
    
    def start_building(self, player, house_type):
        """بدء بناء بيت جديد"""
        # تحقق من الموارد
        can, msg = self.can_build(player, house_type)
        if not can:
            return False, msg
        
        house = self.HOUSE_TYPES[house_type]
        first_stage = house["stages"][0]
        resources = house["resources"][first_stage]
        
        # خصم الموارد
        for item, amt in resources.items():
            player.remove_item(item, amt)
        
        # بدء الجلسة
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
        """حالة البناء الحالية"""
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
        """إكمال المرحلة الحالية"""
        if player.user_id not in self.building_progress:
            return False, "❌ لا يوجد بناء قيد التنفيذ"
        
        progress = self.building_progress[player.user_id]
        status = self.get_building_status(player)
        
        if not status["is_complete"]:
            return False, f"⏳ انتظر {status['time_left']} ثانية لإكمال المرحلة"
        
        # انتقل للمرحلة التالية
        stage_index = progress["stage_index"]
        stages = progress["stages"]
        
        if stage_index + 1 >= len(stages):
            # البيت اكتمل!
            house = self.HOUSE_TYPES[progress["house_type"]]
            bonus = house["bonus"]
            
            # تطبيق المكافآت
            player.max_health += bonus.get("health", 0)
            player.current_health += bonus.get("health", 0)
            player.strength += bonus.get("strength", 0)
            player.speed += bonus.get("speed", 0)
            player.luck += bonus.get("luck", 0)
            
            # حذف الجلسة
            del self.building_progress[player.user_id]
            self.session.commit()
            
            return True, f"🎉 اكتمل بناء {house['name']}!\n\nمكافآت:\n❤️ +{bonus.get('health', 0)} صحة\n🛡️ +{bonus.get('defense', 0)} دفاع\n🍀 +{bonus.get('luck', 0)} حظ"
        
        # المرحلة التالية
        next_stage = stages[stage_index + 1]
        progress["current_stage"] = next_stage
        progress["stage_index"] = stage_index + 1
        progress["started_at"] = datetime.utcnow()
        
        # خصم موارد المرحلة التالية
        house = self.HOUSE_TYPES[progress["house_type"]]
        resources = house["resources"].get(next_stage, {})
        
        for item, amt in resources.items():
            if not player.has_item(item, amt):
                return False, f"❌ ليس لديك موارد كافية للمرحلة التالية\nتحتاج: {item} x{amt}"
            player.remove_item(item, amt)
        
        stage_info = self.BUILDING_STAGES[next_stage]
        self.session.commit()
        
        return True, f"✅ اكتملت {self.BUILDING_STAGES[stages[stage_index]]['name']}!\n\n🏗️ المرحلة التالية: {stage_info['name']}\n⏳ انتظر {stage_info['time']} ثانية\n📦 الموارد المستخدمة: {', '.join([f'{k} x{v}' for k,v in resources.items()])}"
    
    def get_building_stages_info(self, house_type):
        """معلومات عن جميع مراحل البيت"""
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
