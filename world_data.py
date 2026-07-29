import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class Resource:
    name: str
    emoji: str
    min_amount: int
    max_amount: int
    weight: int

@dataclass
class Enemy:
    name: str
    emoji: str
    health: int
    damage: int
    xp: int
    drops: List[Tuple[str, int, float]]
    special: Optional[str] = None

@dataclass
class Tree:
    name: str
    emoji: str
    total_blocks: int
    resources: List[Tuple[str, int]]  # (resource, amount per block)
    rare_drop: Optional[Tuple[str, int, float]] = None  # (resource, amount, probability)

@dataclass
class Rock:
    name: str
    emoji: str
    total_blocks: int
    resources: List[Tuple[str, int]]
    rare_drop: Optional[Tuple[str, int, float]] = None

@dataclass
class Area:
    name: str
    emoji: str
    level_req: int
    trees: List[Tree]
    rocks: List[Rock]
    animals: List[Resource]
    enemies: List[Enemy]
    night_enemies: List[Enemy]
    events: List[dict]
    sub_locations: List[str]

class WorldData:
    AREAS = {
        "forest": Area(
            name="الغابة", emoji="🌳", level_req=1,
            sub_locations=["🌲 أشجار البلوط", "🌲 أشجار التنوب", "🌲 أشجار البتولا", "🐄 المرعى", "🍯 خلايا النحل"],
            trees=[
                Tree("شجرة بلوط", "🌳", random.randint(5, 8),
                     [("oak_wood", 1)],
                     ("apple", 1, 0.3)),
                Tree("شجرة تنوب", "🌲", random.randint(5, 8),
                     [("spruce_wood", 1)],
                     ("mushroom", 1, 0.3)),
                Tree("شجرة بتولا", "🪵", random.randint(5, 8),
                     [("birch_wood", 1)],
                     ("sap", 1, 0.25)),
                Tree("شجرة استوائية", "🌴", random.randint(5, 8),
                     [("jungle_wood", 1)],
                     ("tropical_fruit", 1, 0.2)),
            ],
            rocks=[],
            animals=[
                Resource("بقرة 🐄", "🐄", 1, 1, 25),
                Resource("خنزير 🐷", "🐷", 1, 1, 20),
                Resource("دجاجة 🐔", "🐔", 1, 1, 22),
                Resource("غنم 🐑", "🐑", 1, 1, 18),
                Resource("حصان 🐴", "🐴", 1, 1, 5),
                Resource("ذئب 🐺", "🐺", 1, 1, 3),
                Resource("دب 🐻", "🐻", 1, 1, 7),
            ],
            enemies=[
                Enemy("ذئب", "🐺", 8, 3, 5, [("bone",2,0.5)], "tameable"),
                Enemy("دب", "🐻", 20, 7, 15, [("bear_meat",2,0.8), ("bear_pelt",1,0.4)]),
            ],
            night_enemies=[
                Enemy("زومبي", "🧟", 10, 3, 8, [("rotten_flesh",1,0.5)]),
                Enemy("سكلتون", "💀", 12, 4, 10, [("bone",2,0.6), ("arrow",2,0.4)]),
                Enemy("كريبر", "💚", 15, 8, 15, [("gunpowder",2,0.7)], "explode"),
                Enemy("عنكبوت", "🕷️", 8, 2, 6, [("spider_silk",2,0.5), ("spider_eye",1,0.3)]),
            ],
            events=[
                {"name":"عاصفة","msg":"🌧️ عاصفة! الموارد أقل"},
                {"name":"قوس قزح","msg":"🌈 قوس قزح! ذهب إضافي"},
                {"name":"قطيع ذئاب","msg":"🐺 قطيع ذئاب يهاجمك!"},
            ]
        ),
        "cave": Area(
            name="الكهف", emoji="🕳️", level_req=5,
            sub_locations=["⛏️ منجم", "🕳️ نفق مظلم", "💎 غرفة الكنوز"],
            trees=[],
            rocks=[
                Rock("حجر عادي", "🪨", random.randint(3, 6),
                     [("stone", 1)]),
                Rock("حجر جيري", "🪨", random.randint(3, 6),
                     [("limestone", 1)]),
                Rock("حجر رملي", "🏜️", random.randint(3, 6),
                     [("sandstone", 1)]),
                Rock("حجر فحم", "🖤", random.randint(3, 6),
                     [("stone", 1), ("coal", 1)]),
                Rock("حجر حديد", "⛏️", random.randint(3, 6),
                     [("stone", 1), ("iron_ore", 1)]),
                Rock("حجر ذهب", "✨", random.randint(3, 6),
                     [("stone", 1), ("gold_ore", 1)],
                     ("diamond", 1, 0.05)),
                Rock("حجر ألماس", "💎", random.randint(3, 6),
                     [("stone", 1), ("diamond", 1)],
                     ("emerald", 1, 0.03)),
            ],
            animals=[],
            enemies=[
                Enemy("زومبي", "🧟", 10, 3, 8, [("rotten_flesh",1,0.5)]),
                Enemy("سكلتون", "💀", 12, 4, 10, [("bone",2,0.6)]),
                Enemy("كريبر", "💚", 15, 8, 15, [("gunpowder",2,0.7)], "explode"),
                Enemy("عنكبوت", "🕷️", 8, 2, 6, [("spider_silk",2,0.5)]),
                Enemy("سيلفر فيش", "🪲", 4, 1, 3, [], "steal"),
            ],
            night_enemies=[
                Enemy("زومبي حديدي", "🧟‍♂️", 18, 5, 12, [("iron_ore",1,0.3)]),
                Enemy("سكلتون ناري", "💀🔥", 15, 6, 14, [("bone",3,0.7)]),
            ],
            events=[
                {"name":"صندوق خشبي","msg":"📦 وجدت صندوقاً!"},
                {"name":"صندوق حديدي","msg":"📦 صندوق حديدي!"},
                {"name":"انهيار","msg":"💥 انهيار صخري!"},
            ]
        ),
    }
    
    @classmethod
    def get_area(cls, name):
        return cls.AREAS.get(name)
    
    @classmethod
    def roll_tree(cls, area):
        return random.choice(area.trees)
    
    @classmethod
    def roll_rock(cls, area):
        return random.choice(area.rocks)
    
    @classmethod
    def roll_animal(cls, area):
        if area.animals:
            return random.choice(area.animals)
        return None
    
    @classmethod
    def roll_enemy(cls, area, is_night=False):
        pool = area.night_enemies if is_night else area.enemies
        if pool and random.random() < (0.6 if is_night else 0.3):
            return random.choice(pool)
        return None

    # ===== بيانات الحيوانات =====
    ANIMAL_LOOT = {
        "بقرة 🐄": [("leather", 2), ("raw_beef", 3), ("milk", 1)],
        "خنزير 🐷": [("raw_pork", 3), ("bone", 2)],
        "دجاجة 🐔": [("raw_chicken", 2), ("feather", 3), ("egg", 2)],
        "غنم 🐑": [("wool", 3), ("raw_mutton", 2)],
        "حصان 🐴": [("saddle", 1), ("hoof", 2)],
        "ذئب 🐺": [("bone", 2)],
        "دب 🐻": [("bear_meat", 3), ("bear_pelt", 2)],
                         }
