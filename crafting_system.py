from typing import Dict, List, Tuple, Optional

class CraftingSystem:
    # تعريف 80 وصفة تصنيع
    RECIPES = {
        # المستوى 1 - الأساسيات (6 وصفات)
        "wooden_planks": {
            "name": "ألواح خشب", "emoji": "🪵",
            "level": "level_1",
            "inputs": {"oak_wood": 1},
            "output": {"wooden_planks": 4},
            "xp": 1,
            "description": "تحويل الخشب إلى ألواح"
        },
        "sticks": {
            "name": "عصي", "emoji": "🥢",
            "level": "level_1",
            "inputs": {"wooden_planks": 2},
            "output": {"sticks": 4},
            "xp": 1,
            "description": "صنع عصي خشبية"
        },
        "crafting_table": {
            "name": "طاولة تصنيع", "emoji": "🔨",
            "level": "level_1",
            "inputs": {"wooden_planks": 4},
            "output": {"crafting_table": 1},
            "xp": 2,
            "description": "طاولة للتصنيع المتقدم"
        },
        "furnace": {
            "name": "فرن", "emoji": "🔥",
            "level": "level_1",
            "inputs": {"stone": 8},
            "output": {"furnace": 1},
            "xp": 2,
            "description": "لصهر المعادن وطهي الطعام"
        },
        "wooden_fence": {
            "name": "سياج خشبي", "emoji": "🚧",
            "level": "level_1",
            "inputs": {"sticks": 6},
            "output": {"wooden_fence": 3},
            "xp": 1,
            "description": "سياج للحماية"
        },
        "wooden_door": {
            "name": "باب خشبي", "emoji": "🚪",
            "level": "level_1",
            "inputs": {"wooden_planks": 6},
            "output": {"wooden_door": 1},
            "xp": 2,
            "description": "باب للمباني"
        },
        
        # المستوى 2 - أدوات خشبية (6 وصفات)
        "wooden_axe": {
            "name": "فأس خشبي", "emoji": "🪓",
            "level": "level_2",
            "inputs": {"wooden_planks": 3, "sticks": 2},
            "output": {"wooden_axe": 1},
            "xp": 3,
            "durability": 60,
            "description": "لتقطيع الأشجار بسرعة"
        },
        "wooden_pickaxe": {
            "name": "معول خشبي", "emoji": "⛏️",
            "level": "level_2",
            "inputs": {"wooden_planks": 3, "sticks": 2},
            "output": {"wooden_pickaxe": 1},
            "xp": 3,
            "durability": 60,
            "description": "لتعدين الحجر"
        },
        "wooden_sword": {
            "name": "سيف خشبي", "emoji": "🗡️",
            "level": "level_2",
            "inputs": {"wooden_planks": 2, "sticks": 1},
            "output": {"wooden_sword": 1},
            "xp": 3,
            "durability": 60,
            "damage": 4,
            "description": "سيف بسيط للقتال"
        },
        "wooden_hoe": {
            "name": "مجرفة خشبية", "emoji": "🔧",
            "level": "level_2",
            "inputs": {"wooden_planks": 2, "sticks": 2},
            "output": {"wooden_hoe": 1},
            "xp": 2,
            "durability": 60,
            "description": "للزراعة"
        },
        "bow": {
            "name": "قوس", "emoji": "🏹",
            "level": "level_2",
            "inputs": {"sticks": 3, "spider_silk": 3},
            "output": {"bow": 1},
            "xp": 4,
            "durability": 384,
            "damage": 6,
            "description": "سلاح بعيد المدى"
        },
        "arrows": {
            "name": "سهام (8)", "emoji": "🏹",
            "level": "level_2",
            "inputs": {"sticks": 1, "feather": 1, "stone": 1},
            "output": {"arrows": 8},
            "xp": 2,
            "description": "ذخيرة القوس"
        },
        
        # المستوى 3 - أدوات حجرية وحديدية أساسية (8 وصفات)
        "stone_axe": {
            "name": "فأس حجري", "emoji": "🪓",
            "level": "level_3",
            "inputs": {"stone": 3, "sticks": 2},
            "output": {"stone_axe": 1},
            "xp": 5,
            "durability": 132,
            "description": "فأس أقوى"
        },
        "stone_pickaxe": {
            "name": "معول حجري", "emoji": "⛏️",
            "level": "level_3",
            "inputs": {"stone": 3, "sticks": 2},
            "output": {"stone_pickaxe": 1},
            "xp": 5,
            "durability": 132,
            "description": "لتعدين الحديد"
        },
        "stone_sword": {
            "name": "سيف حجري", "emoji": "🗡️",
            "level": "level_3",
            "inputs": {"stone": 2, "sticks": 1},
            "output": {"stone_sword": 1},
            "xp": 5,
            "durability": 132,
            "damage": 5,
            "description": "سيف متوسط القوة"
        },
        "iron_axe": {
            "name": "فأس حديدي", "emoji": "🪓",
            "level": "level_3",
            "inputs": {"iron_ingot": 3, "sticks": 2},
            "output": {"iron_axe": 1},
            "xp": 7,
            "durability": 251,
            "description": "فأس قوي"
        },
        "iron_chestplate": {
            "name": "درع صدر حديدي", "emoji": "🛡️",
            "level": "level_3",
            "inputs": {"iron_ingot": 8},
            "output": {"iron_chestplate": 1},
            "xp": 8,
            "durability": 241,
            "defense": 6,
            "description": "حماية متوسطة"
        },
        "bread": {
            "name": "خبز", "emoji": "🍞",
            "level": "level_3",
            "inputs": {"wheat": 3},
            "output": {"bread": 1},
            "xp": 3,
            "food_value": 5,
            "description": "طعام جيد"
        },
        "cooked_beef": {
            "name": "لحم بقر مطبوخ", "emoji": "🥩",
            "level": "level_3",
            "inputs": {"raw_beef": 1, "coal": 1},
            "output": {"cooked_beef": 1},
            "xp": 4,
            "food_value": 8,
            "description": "لحم شهي"
        },
        "torch": {
            "name": "شعلة (4)", "emoji": "🔦",
            "level": "level_3",
            "inputs": {"coal": 1, "sticks": 1},
            "output": {"torch": 4},
            "xp": 2,
            "description": "للإضاءة"
        },
        
        # المستوى 4 - أدوات حديدية وألماسية أساسية (8 وصفات)
        "iron_sword": {
            "name": "سيف حديدي", "emoji": "🗡️",
            "level": "level_4",
            "inputs": {"iron_ingot": 2, "sticks": 1},
            "output": {"iron_sword": 1},
            "xp": 8,
            "durability": 251,
            "damage": 6,
            "description": "سيف قوي"
        },
        "full_iron_armor": {
            "name": "درع حديدي كامل", "emoji": "🛡️",
            "level": "level_4",
            "inputs": {"iron_ingot": 24},
            "output": {"iron_helmet": 1, "iron_chestplate": 1, 
                      "iron_leggings": 1, "iron_boots": 1},
            "xp": 15,
            "description": "مجموعة درع كاملة"
        },
        "diamond_axe": {
            "name": "فأس ألماسي", "emoji": "🪓",
            "level": "level_4",
            "inputs": {"diamond": 3, "sticks": 2},
            "output": {"diamond_axe": 1},
            "xp": 12,
            "durability": 1562,
            "description": "أفضل فأس"
        },
        "diamond_pickaxe": {
            "name": "معول ألماسي", "emoji": "⛏️",
            "level": "level_4",
            "inputs": {"diamond": 3, "sticks": 2},
            "output": {"diamond_pickaxe": 1},
            "xp": 12,
            "durability": 1562,
            "description": "لتعدين الألماس"
        },
        "golden_apple": {
            "name": "تفاح ذهبي", "emoji": "🍎",
            "level": "level_4",
            "inputs": {"apple": 1, "gold_ingot": 8},
            "output": {"golden_apple": 1},
            "xp": 20,
            "food_value": 4,
            "effect": "regeneration",
            "description": "يعالج الصحة"
        },
        "healing_potion": {
            "name": "جرعة شفاء", "emoji": "🧪",
            "level": "level_4",
            "inputs": {"sap": 2, "mushroom": 1, "glass_bottle": 1},
            "output": {"healing_potion": 1},
            "xp": 8,
            "heal_amount": 10,
            "description": "يستعيد 10 قلوب"
        },
        "compass": {
            "name": "بوصلة", "emoji": "🧭",
            "level": "level_4",
            "inputs": {"iron_ingot": 4, "redstone": 1},
            "output": {"compass": 1},
            "xp": 5,
            "description": "تقلل وقت الاستكشاف 20%"
        },
        "saddle": {
            "name": "سرج", "emoji": "🐴",
            "level": "level_4",
            "inputs": {"leather": 5, "iron_ingot": 2},
            "output": {"saddle": 1},
            "xp": 10,
            "description": "يسرع الاستكشاف 50%"
        },
        
        # المستوى 5 - متطور (8 وصفات)
        "diamond_sword": {
            "name": "سيف ألماسي", "emoji": "🗡️",
            "level": "level_5",
            "inputs": {"diamond": 2, "sticks": 1},
            "output": {"diamond_sword": 1},
            "xp": 15,
            "durability": 1562,
            "damage": 7,
            "description": "أفضل سيف"
        },
        "diamond_armor_full": {
            "name": "درع ألماسي كامل", "emoji": "💎",
            "level": "level_5",
            "inputs": {"diamond": 24},
            "output": {"diamond_helmet": 1, "diamond_chestplate": 1,
                      "diamond_leggings": 1, "diamond_boots": 1},
            "xp": 25,
            "description": "أفضل حماية"
        },
        "nether_portal": {
            "name": "بوابة النذر", "emoji": "🔥",
            "level": "level_5",
            "inputs": {"obsidian": 10, "flint_and_steel": 1},
            "output": {"nether_portal": 1},
            "xp": 20,
            "description": "تفتح بوابة إلى النذر"
        },
        "ender_portal": {
            "name": "بوابة الإندر", "emoji": "🌌",
            "level": "level_5",
            "inputs": {"ender_pearl": 12, "blaze_powder": 12},
            "output": {"ender_portal": 1},
            "xp": 25,
            "description": "تفتح بوابة إلى الإندر"
        },
        "eye_of_ender": {
            "name": "عين الإندر", "emoji": "👁️",
            "level": "level_5",
            "inputs": {"ender_pearl": 1, "blaze_powder": 1},
            "output": {"eye_of_ender": 1},
            "xp": 3,
            "description": "للبحث عن القلعة"
        },
        "elytra": {
            "name": "جناح الطيران", "emoji": "🪽",
            "level": "level_5",
            "inputs": {"phantom_membrane": 7, "diamond": 1},
            "output": {"elytra": 1},
            "xp": 30,
            "description": "للطيران - يضاعف سرعة الاستكشاف"
        },
        "fire_resistance_armor": {
            "name": "درع ناري", "emoji": "🔥",
            "level": "level_5",
            "inputs": {"fiery_coal": 5, "iron_ingot": 8},
            "output": {"fire_resistance_chestplate": 1},
            "xp": 18,
            "description": "يحصن ضد النار"
        },
        "ender_sword": {
            "name": "سيف الإندر", "emoji": "⚔️",
            "level": "level_5",
            "inputs": {"diamond_sword": 1, "ender_pearl": 5, "diamond": 2},
            "output": {"ender_sword": 1},
            "xp": 35,
            "durability": 2000,
            "damage": 10,
            "description": "السيف الأعظم - لهلاك التنين"
        },
    }
    
    @classmethod
    def get_recipe(cls, recipe_name: str) -> Optional[Dict]:
        return cls.RECIPES.get(recipe_name)
    
    @classmethod
    def get_recipes_by_level(cls, level: str) -> List[Dict]:
        return [recipe for recipe in cls.RECIPES.values() if recipe["level"] == level]
    
    @classmethod
    def can_craft(cls, player, recipe_name: str) -> Tuple[bool, str]:
        """التحقق من إمكانية التصنيع"""
        recipe = cls.get_recipe(recipe_name)
        if not recipe:
            return False, "الوصفة غير موجودة"
        
        if recipe["level"] not in player.recipes_unlocked:
            return False, "لم تفتح هذا المستوى من التصنيع بعد"
        
        # التحقق من المواد المطلوبة
        for item, amount in recipe["inputs"].items():
            if not cls.has_items(player, item, amount):
                return False, f"تحتاج {amount} {item}"
        
        return True, "يمكنك التصنيع"
    
    @classmethod
    def has_items(cls, player, item_name: str, amount: int) -> bool:
        """التحقق من وجود المواد في المخزون"""
        total = 0
        for slot, item_data in player.inventory.items():
            if item_data and item_data.get("name") == item_name:
                total += item_data.get("amount", 0)
        return total >= amount
    
    @classmethod
    def remove_items(cls, player, item_name: str, amount: int) -> bool:
        """إزالة المواد من المخزون"""
        remaining = amount
        for slot, item_data in player.inventory.items():
            if item_data and item_data.get("name") == item_name:
                current = item_data.get("amount", 0)
                if current <= remaining:
                    player.inventory[slot] = None
                    remaining -= current
                else:
                    player.inventory[slot]["amount"] -= remaining
                    remaining = 0
                if remaining == 0:
                    return True
        return False
    
    @classmethod
    def add_item(cls, player, item_name: str, amount: int):
        """إضافة عنصر للمخزون"""
        # البحث عن خانة فارغة أو خانة بها نفس العنصر
        for slot in range(36):
            slot_key = f"slot_{slot}"
            item_data = player.inventory[slot_key]
            
            if item_data is None:
                player.inventory[slot_key] = {"name": item_name, "amount": amount}
                return True
            elif item_data["name"] == item_name and item_data.get("amount", 0) < 64:
                space = 64 - item_data["amount"]
                if amount <= space:
                    player.inventory[slot_key]["amount"] += amount
                    return True
                else:
                    player.inventory[slot_key]["amount"] = 64
                    amount -= space
        
        return False  # المخزون ممتلئ
