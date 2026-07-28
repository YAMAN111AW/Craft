import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class Resource:
    name: str
    emoji: str
    min_amount: int
    max_amount: int
    weight: int  # higher = more common

@dataclass
class Enemy:
    name: str
    emoji: str
    health: int
    damage: int
    xp: int
    drops: List[Tuple[str, int, float]]  # name, amount, probability 0-1
    special: Optional[str] = None

@dataclass
class Area:
    name: str
    emoji: str
    level_req: int
    explore_time: int  # seconds base
    resources: List[Resource]
    enemies: List[Enemy]
    events: List[Dict]
    sub_locations: List[str] = field(default_factory=list)

class WorldData:
    @staticmethod
    def get_all_areas():
        return {
            "forest": Area(
                name="الغابة", emoji="🌳", level_req=1, explore_time=30,
                sub_locations=["أشجار", "مرعى الحيوانات", "خلايا النحل", "بركة"],
                resources=[
                    Resource("oak_wood", "🪵", 3, 6, 30),
                    Resource("spruce_wood", "🪵", 3, 6, 25),
                    Resource("birch_wood", "🪵", 3, 6, 20),
                    Resource("jungle_wood", "🪵", 3, 6, 15),
                    Resource("apple", "🍎", 1, 2, 15),
                    Resource("mushroom", "🍄", 1, 2, 20),
                    Resource("sap", "💧", 1, 2, 15),
                    Resource("tropical_fruit", "🥭", 1, 1, 10),
                    Resource("leather", "🟤", 1, 3, 20),
                    Resource("raw_beef", "🥩", 2, 4, 18),
                    Resource("milk", "🥛", 1, 1, 12),
                    Resource("raw_pork", "🥩", 2, 3, 15),
                    Resource("bone", "🦴", 1, 3, 15),
                    Resource("raw_chicken", "🍗", 1, 2, 20),
                    Resource("feather", "🪶", 1, 3, 15),
                    Resource("egg", "🥚", 1, 2, 14),
                    Resource("wool", "🧶", 1, 3, 18),
                    Resource("raw_mutton", "🥩", 2, 3, 14),
                    Resource("saddle", "🐴", 1, 1, 3),
                    Resource("hoof", "🦶", 1, 2, 5),
                    Resource("bear_meat", "🥩", 3, 5, 5),
                    Resource("bear_pelt", "🟤", 1, 2, 5),
                    Resource("honey", "🍯", 1, 2, 10),
                    Resource("spider_silk", "🕸️", 1, 3, 12),
                ],
                enemies=[
                    Enemy("ذئب", "🐺", 8, 3, 5, [("bone",2,0.5)], "tameable"),
                    Enemy("دب", "🐻", 20, 7, 15, [("bear_meat",2,0.8),("bear_pelt",1,0.4)]),
                ],
                events=[
                    {"name":"عاصفة","msg":"🌧️ عاصفة! زاد وقت الاستكشاف","eff":"slow"},
                    {"name":"قوس قزح","msg":"🌈 قوس قزح! ذهب إضافي","eff":"gold"},
                    {"name":"قطيع ذئاب","msg":"🐺 قطيع ذئاب يهاجمك!","eff":"wolf_attack"},
                    {"name":"زلزال","msg":"🌍 زلزال! معادن مكشوفة","eff":"minerals"},
                ]
            ),
            "cave": Area(
                name="الكهف", emoji="🕳️", level_req=5, explore_time=45,
                sub_locations=["منجم", "نفق مظلم", "بحيرة جوفية", "غرفة الكنوز"],
                resources=[
                    Resource("stone", "🪨", 3, 6, 35),
                    Resource("limestone", "🪨", 2, 5, 25),
                    Resource("sandstone", "🏜️", 2, 5, 25),
                    Resource("coal", "🖤", 1, 3, 25),
                    Resource("iron_ore", "⛏️", 1, 2, 18),
                    Resource("gold_ore", "✨", 1, 2, 8),
                    Resource("diamond", "💎", 1, 1, 2),
                    Resource("emerald", "💚", 1, 1, 3),
                    Resource("quartz", "⬜", 1, 2, 10),
                ],
                enemies=[
                    Enemy("زومبي", "🧟", 10, 3, 8, [("rotten_flesh",1,0.5)]),
                    Enemy("سكلتون", "💀", 12, 4, 10, [("bone",2,0.6),("arrow",2,0.4)]),
                    Enemy("كريبر", "💚", 15, 8, 15, [("gunpowder",2,0.7)], "explode"),
                    Enemy("عنكبوت", "🕷️", 8, 2, 6, [("spider_silk",2,0.5),("spider_eye",1,0.3)]),
                    Enemy("سيلفر فيش", "🪲", 4, 1, 3, [], "steal"),
                ],
                events=[
                    {"name":"صندوق خشبي","msg":"📦 وجدت صندوقاً خشبياً!","eff":"chest_basic"},
                    {"name":"صندوق حديدي","msg":"📦 صندوق حديدي!","eff":"chest_iron"},
                    {"name":"صندوق منحوت","msg":"📦 صندوق منحوت نادر!","eff":"chest_rare"},
                ]
            ),
            "nether": Area(
                name="النذر", emoji="🔥", level_req=15, explore_time=60,
                sub_locations=["أرض الحمم", "حصون النذر", "غابات نارية"],
                resources=[
                    Resource("crimson_wood", "🔥", 2, 4, 20),
                    Resource("fiery_coal", "🔥", 1, 2, 15),
                    Resource("quartz", "⬜", 1, 3, 20),
                    Resource("netherrack", "🟥", 2, 4, 30),
                    Resource("blaze_rod", "🔥", 1, 1, 8),
                    Resource("ghast_tear", "💧", 1, 1, 5),
                ],
                enemies=[
                    Enemy("بليز", "🔥", 20, 6, 20, [("blaze_rod",1,0.5)], "fire"),
                    Enemy("غاست", "👻", 15, 8, 18, [("ghast_tear",1,0.4)], "flying"),
                    Enemy("زومبي ناري", "🧟‍♂️", 18, 5, 15, [("rotten_flesh",1,0.5)], "fire"),
                ],
                events=[
                    {"name":"عاصفة حمم","msg":"🌋 عاصفة حمم!","eff":"lava_storm"},
                ]
            ),
            "end": Area(
                name="الإندر", emoji="🌌", level_req=25, explore_time=70,
                sub_locations=["جزر عائمة", "مدينة الإندر"],
                resources=[
                    Resource("ender_stone", "🟪", 2, 4, 25),
                    Resource("ender_pearl", "🔮", 1, 2, 10),
                    Resource("diamond", "💎", 1, 1, 5),
                ],
                enemies=[
                    Enemy("إندرمان", "⬛", 20, 7, 25, [("ender_pearl",1,0.5)], "teleport"),
                ],
                events=[
                    {"name":"سفينة الإندر","msg":"🚀 وجدت سفينة الإندر!","eff":"ender_ship"},
                ]
            ),
        }

    @classmethod
    def get_area(cls, name: str):
        return cls.get_all_areas().get(name)
    
    @classmethod
    def roll_resource(cls, area: Area, luck=0):
        total_w = sum(r.weight + luck for r in area.resources)
        roll = random.randint(1, total_w)
        current = 0
        for r in area.resources:
            current += r.weight + luck
            if roll <= current:
                return r
        return area.resources[0]
    
    @classmethod
    def roll_enemy(cls, area: Area):
        if random.random() < 0.35:
            return random.choice(area.enemies)
        return None
