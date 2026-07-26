# بيانات المناطق والموارد والأعداء المتوازنة
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple

@dataclass
class Resource:
    name: str
    emoji: str
    min_amount: int
    max_amount: int
    rarity: float  # 0-1, كلما قل الرقم كان أندر
    category: str  # wood, stone, food, rare, etc.

@dataclass
class Enemy:
    name: str
    emoji: str
    health: int
    damage: int
    xp_reward: int
    drops: List[Tuple[str, int, float]]  # (item, amount, probability)
    special_ability: Optional[str] = None

@dataclass
class Area:
    name: str
    emoji: str
    description: str
    resources: List[Resource]
    enemies: List[Enemy]
    level_required: int
    exploration_time: int  # بالثواني
    random_events: List[Dict]
    
class WorldData:
    # تعريف جميع الموارد
    RESOURCES = {
        # الغابة
        "oak_wood": Resource("خشب بلوط", "🪵", 3, 6, 0.8, "wood"),
        "spruce_wood": Resource("خشب تنوب", "🪵", 3, 6, 0.7, "wood"),
        "birch_wood": Resource("خشب بتولا", "🪵", 3, 6, 0.6, "wood"),
        "jungle_wood": Resource("خشب استوائي", "🪵", 3, 6, 0.5, "wood"),
        "crimson_wood": Resource("خشب ناري", "🔥", 2, 4, 0.3, "wood"),
        "apple": Resource("تفاح", "🍎", 1, 2, 0.3, "food"),
        "mushroom": Resource("فطر", "🍄", 1, 2, 0.4, "food"),
        "sap": Resource("عصارة", "💧", 1, 2, 0.35, "material"),
        "tropical_fruit": Resource("فاكهة استوائية", "🥭", 1, 1, 0.25, "food"),
        "fiery_coal": Resource("فحم ناري", "🔥", 1, 2, 0.2, "material"),
        
        # حيوانات الغابة
        "leather": Resource("جلد", "🟤", 1, 3, 0.7, "material"),
        "raw_beef": Resource("لحم بقر ني", "🥩", 2, 4, 0.6, "food"),
        "milk": Resource("حليب", "🥛", 1, 1, 0.4, "food"),
        "raw_pork": Resource("لحم خنزير ني", "🥩", 2, 3, 0.6, "food"),
        "bone": Resource("عظم", "🦴", 1, 3, 0.5, "material"),
        "raw_chicken": Resource("لحم دجاج ني", "🍗", 1, 2, 0.7, "food"),
        "feather": Resource("ريش", "🪶", 1, 3, 0.5, "material"),
        "egg": Resource("بيض", "🥚", 1, 2, 0.4, "food"),
        "wool": Resource("صوف", "🧶", 1, 3, 0.6, "material"),
        "raw_mutton": Resource("لحم ضأن ني", "🥩", 2, 3, 0.5, "food"),
        "saddle": Resource("سرج", "🐴", 1, 1, 0.1, "rare"),
        "hoof": Resource("حافر", "🦶", 1, 2, 0.15, "material"),
        "bear_meat": Resource("لحم دب", "🥩", 3, 5, 0.3, "food"),
        "bear_pelt": Resource("جلد دب", "🟤", 1, 2, 0.3, "rare"),
        
        # زهور وفطر
        "flower_red": Resource("زهرة حمراء", "🌹", 1, 2, 0.6, "material"),
        "flower_blue": Resource("زهرة زرقاء", "🌸", 1, 2, 0.5, "material"),
        "poisonous_mushroom": Resource("فطر سام", "☠️", 1, 1, 0.3, "material"),
        "honey": Resource("عسل", "🍯", 1, 2, 0.25, "food"),
        "spider_silk": Resource("خيط عنكبوت", "🕸️", 1, 3, 0.4, "material"),
        
        # الكهف
        "stone": Resource("حجر خام", "🪨", 3, 6, 0.9, "stone"),
        "limestone": Resource("حجر جيري", "🪨", 2, 5, 0.7, "stone"),
        "sandstone": Resource("حجر رملي", "🏜️", 2, 5, 0.7, "stone"),
        "coal": Resource("فحم", "🖤", 1, 3, 0.6, "mineral"),
        "iron_ore": Resource("حديد خام", "⛏️", 1, 2, 0.4, "mineral"),
        "gold_ore": Resource("ذهب خام", "✨", 1, 2, 0.2, "mineral"),
        "diamond": Resource("ألماس", "💎", 1, 1, 0.05, "rare"),
        "emerald": Resource("زمرد", "💚", 1, 1, 0.08, "rare"),
        "netherrack": Resource("حجر الهاوية", "🟥", 2, 4, 0.5, "special"),
        "quartz": Resource("كوارتز", "⬜", 1, 2, 0.3, "mineral"),
    }
    
    # تعريف جميع الأعداء
    ENEMIES = {
        "zombie": Enemy("زومبي", "🧟", 10, 3, 5, 
                       [("rotten_flesh", 1, 0.6), ("iron_ingot", 1, 0.1)]),
        "baby_zombie": Enemy("زومبي طفل", "🧒", 5, 2, 8, 
                            [("rotten_flesh", 1, 0.5)], "fast"),
        "skeleton": Enemy("سكلتون", "💀", 12, 4, 7, 
                         [("bone", 2, 0.7), ("arrow", 2, 0.5)]),
        "creeper": Enemy("كريبر", "💚", 15, 20, 10, 
                        [("gunpowder", 2, 0.8)], "explode"),
        "spider": Enemy("عنكبوت", "🕷️", 8, 2, 5, 
                       [("spider_silk", 2, 0.6), ("spider_eye", 1, 0.3)]),
        "blaze": Enemy("بليز", "🔥", 20, 6, 15, 
                      [("blaze_rod", 1, 0.5)], "fire_burst"),
        "ghast": Enemy("غاست", "👻", 15, 8, 12, 
                      [("ghast_tear", 1, 0.4)], "flying"),
        "enderman": Enemy("إندرمان", "⬛", 20, 7, 15, 
                         [("ender_pearl", 1, 0.4)], "teleport"),
        "ender_dragon": Enemy("تنين الإندر", "🐉", 100, 15, 100, 
                             [("dragon_egg", 1, 1.0)], "boss"),
    }
    
    AREAS = {
        "forest": Area(
            name="الغابة",
            emoji="🌳",
            description="غابة كثيفة مليئة بالأشجار والحيوانات",
            level_required=1,
            exploration_time=30,
            resources=[
                RESOURCES["oak_wood"], RESOURCES["spruce_wood"],
                RESOURCES["apple"], RESOURCES["mushroom"],
                RESOURCES["leather"], RESOURCES["raw_beef"],
                RESOURCES["feather"], RESOURCES["wool"],
                RESOURCES["honey"], RESOURCES["spider_silk"]
            ],
            enemies=[
                ENEMIES["zombie"], ENEMIES["skeleton"],
                ENEMIES["creeper"], ENEMIES["spider"]
            ],
            random_events=[
                {"name": "عاصفة", "effect": "slow_explore", "probability": 0.15},
                {"name": "نار غابة", "effect": "reduce_resources", "probability": 0.1},
                {"name": "قوس قزح", "effect": "gold_bonus", "probability": 0.05},
                {"name": "زلزال", "effect": "reveal_minerals", "probability": 0.08},
                {"name": "قطيع ذئاب", "effect": "wolf_attack", "probability": 0.07}
            ]
        ),
        "cave": Area(
            name="الكهف",
            emoji="🕳️",
            description="كهف مظلم مليء بالمعادن والأخطار",
            level_required=5,
            exploration_time=45,
            resources=[
                RESOURCES["stone"], RESOURCES["coal"],
                RESOURCES["iron_ore"], RESOURCES["gold_ore"],
                RESOURCES["diamond"], RESOURCES["emerald"],
                RESOURCES["quartz"]
            ],
            enemies=[
                ENEMIES["zombie"], ENEMIES["skeleton"],
                ENEMIES["spider"], ENEMIES["creeper"]
            ],
            random_events=[
                {"name": "صندوق خشبي", "effect": "treasure_basic", "probability": 0.2},
                {"name": "صندوق حديدي", "effect": "treasure_medium", "probability": 0.1},
                {"name": "صندوق منحوت", "effect": "treasure_rare", "probability": 0.05},
                {"name": "صندوق سحري", "effect": "treasure_legendary", "probability": 0.02}
            ]
        )
    }
    
    @classmethod
    def get_area(cls, area_name: str) -> Optional[Area]:
        return cls.AREAS.get(area_name)
    
    @classmethod
    def get_random_resource(cls, area: Area, player_luck: int = 0) -> Optional[Resource]:
        """اختيار مورد عشوائي مع مراعاة الحظ"""
        luck_bonus = player_luck * 0.01  # كل نقطة حظ تزيد 1% فرصة الموارد النادرة
        weighted_resources = []
        
        for resource in area.resources:
            effective_rarity = resource.rarity + luck_bonus
            weighted_resources.extend([resource] * int(effective_rarity * 100))
        
        return random.choice(weighted_resources) if weighted_resources else None
    
    @classmethod
    def get_random_enemy(cls, area: Area, world_event_bonus: float = 0) -> Optional[Enemy]:
        """اختيار عدو عشوائي مع احتمالية ظهور أعداء نادرين"""
        if random.random() < 0.3 + world_event_bonus:  # 30% فرصة مواجهة عدو
            return random.choice(area.enemies)
        return None
