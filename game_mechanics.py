import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from database import Player, WorldEvent, Session
from world_data import WorldData, Area, Enemy, Resource
from crafting_system import CraftingSystem

class GameMechanics:
    def __init__(self, session: Session):
        self.session = session
        self.world_data = WorldData()
    
    # ============ نظام الاستكشاف ============
    def explore_area(self, player: Player, area_name: str) -> Dict:
        """استكشاف منطقة جديدة"""
        area = self.world_data.get_area(area_name)
        if not area:
            return {"error": "المنطقة غير موجودة"}
        
        if player.level < area.level_required:
            return {"error": f"تحتاج مستوى {area.level_required} لدخول هذه المنطقة"}
        
        # حساب وقت الاستكشاف مع المهارات والمعدات
        explore_time = area.exploration_time
        explore_time *= (1 - player.speed * 0.005)  # نقطة السرعة تقلل 0.5%
        
        # تأثير المعدات
        if player.equipment.get("weapon") and "compass" in str(player.inventory):
            explore_time *= 0.8  # البوصلة تقلل 20%
        if player.inventory_has("saddle"):
            explore_time *= 0.5  # السرج يقلل 50%
        if player.inventory_has("elytra"):
            explore_time *= 0.5  # جناح الطيران يضاعف السرعة
        
        # تقليل الجوع
        hunger_cost = max(1, int(explore_time / 30))
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        
        # جمع الموارد (3-5 موارد)
        num_resources = random.randint(3, 5)
        rewards = []
        for _ in range(num_resources):
            resource = self.world_data.get_random_resource(area, player.luck)
            if resource:
                amount = random.randint(resource.min_amount, resource.max_amount)
                CraftingSystem.add_item(player, resource.name, amount)
                rewards.append(f"{resource.emoji} {resource.name} x{amount}")
        
        # مواجهة الأعداء
        enemy_result = None
        enemy = self.world_data.get_random_enemy(area)
        if enemy:
            enemy_result = self.fight_enemy(player, enemy)
        
        # حدث عشوائي
        event_result = None
        if random.random() < 0.25:  # 25% فرصة حدث عشوائي
            event_result = self.trigger_random_event(player, area)
        
        # حساب الخبرة
        xp_gained = random.randint(5, 15) * (1 + player.luck * 0.02)
        player.add_xp(int(xp_gained))
        
        # تحديث آخر نشاط
        player.last_action = datetime.utcnow()
        
        result = {
            "area": area.name,
            "emoji": area.emoji,
            "explore_time": int(explore_time),
            "rewards": rewards,
            "enemy": enemy_result,
            "event": event_result,
            "xp_gained": int(xp_gained),
            "hunger_cost": hunger_cost,
            "current_hunger": player.current_hunger,
            "current_health": player.current_health
        }
        
        # التحقق من الجوع الحاد
        if player.current_hunger <= 0:
            player.current_health = max(1, player.current_health - 3)
            result["starvation"] = "⚠️ أنت تتضور جوعاً! صحتك تنخفض"
        
        self.session.commit()
        return result
    
    # ============ نظام القتال ============
    def fight_enemy(self, player: Player, enemy: Enemy) -> Dict:
        """نظام قتال متوازن"""
        player_damage = self.calculate_player_damage(player)
        player_defense = self.calculate_player_defense(player)
        
        # جولات القتال
        rounds = []
        player_hp = player.current_health
        enemy_hp = enemy.health
        escaped = False
        
        for round_num in range(1, 6):  # أقصى 5 جولات
            round_result = {"round": round_num}
            
            # دور اللاعب
            player_attack = max(1, player_damage - random.randint(0, 2))
            enemy_hp -= player_attack
            round_result["player_attack"] = player_attack
            
            if enemy_hp <= 0:
                # انتصر اللاعب
                round_result["victory"] = True
                rounds.append(round_result)
                break
            
            # دور العدو
            enemy_attack = max(1, enemy.damage - player_defense // 3)
            player_hp -= enemy_attack
            round_result["enemy_attack"] = enemy_attack
            
            # قدرات خاصة للأعداء
            if enemy.special_ability == "explode" and round_num == 3:
                explosion_damage = enemy.damage * 2
                player_hp -= explosion_damage
                round_result["special"] = f"💥 الكريبر انفجر! ضرر إضافي {explosion_damage}"
            
            elif enemy.special_ability == "fire_burst":
                fire_damage = 3
                player_hp -= fire_damage
                round_result["special"] = f"🔥 هجوم ناري! ضرر {fire_damage}"
            
            rounds.append(round_result)
            
            if player_hp <= 0:
                break
            
            # فرصة هروب (20%)
            if random.random() < 0.2 and round_num >= 2:
                escaped = True
                round_result["escaped"] = True
                break
        
        # تحديث صحة اللاعب
        old_health = player.current_health
        player.current_health = max(1, player_hp)
        
        result = {
            "enemy_name": enemy.name,
            "enemy_emoji": enemy.emoji,
            "rounds": rounds,
            "escaped": escaped
        }
        
        if enemy_hp <= 0:
            # مكافآت القتل
            xp_reward = enemy.xp_reward * (1 + player.luck * 0.03)
            player.add_xp(int(xp_reward))
            
            drops = []
            for item_name, amount, probability in enemy.drops:
                if random.random() < probability * (1 + player.luck * 0.01):
                    CraftingSystem.add_item(player, item_name, amount)
                    drops.append(f"{item_name} x{amount}")
            
            result["victory"] = True
            result["xp_reward"] = int(xp_reward)
            result["drops"] = drops
        else:
            result["victory"] = False
            result["health_lost"] = old_health - player.current_health
        
        return result
    
    def calculate_player_damage(self, player: Player) -> int:
        """حساب ضرر اللاعب"""
        base_damage = 2
        
        # ضرر السلاح
        weapon = player.equipment.get("weapon")
        if weapon:
            weapon_damages = {
                "wooden_sword": 4, "stone_sword": 5, "iron_sword": 6,
                "diamond_sword": 7, "ender_sword": 10, "fiery_sword": 8
            }
            base_damage += weapon_damages.get(weapon, 3)
        
        # إضافة القوة
        base_damage += int(base_damage * player.strength * 0.02)
        
        return base_damage
    
    def calculate_player_defense(self, player: Player) -> int:
        """حساب دفاع اللاعب"""
        defense = 0
        
        # دفاع الدروع
        for slot in ["helmet", "chestplate", "leggings", "boots"]:
            armor = player.equipment.get(slot)
            if armor:
                armor_defenses = {
                    "iron": 2, "diamond": 3, "fire_resistance": 4
                }
                for key, value in armor_defenses.items():
                    if key in str(armor):
                        defense += value
        
        return defense
    
    # ============ الأحداث العشوائية ============
    def trigger_random_event(self, player: Player, area: Area) -> Dict:
        """تفعيل حدث عشوائي"""
        if not area.random_events:
            return {"name": "لا حدث"}
        
        event = random.choice(area.random_events)
        event_name = event["name"]
        
        if event_name == "عاصفة":
            return {"name": event_name, "message": "🌧️ عاصفة! زاد وقت الاستكشاف 50%"}
        
        elif event_name == "نار غابة":
            return {"name": event_name, "message": "🔥 حريق! بعض الموارد احترقت"}
        
        elif event_name == "قوس قزح":
            gold_amount = random.randint(5, 15)
            CraftingSystem.add_item(player, "gold_ingot", gold_amount)
            return {"name": event_name, "message": f"🌈 قوس قزح! حصلت على {gold_amount} سبائك ذهب"}
        
        elif event_name == "زلزال":
            minerals = random.choice(["iron_ore", "gold_ore", "coal"])
            amount = random.randint(2, 5)
            CraftingSystem.add_item(player, minerals, amount)
            return {"name": event_name, "message": f"🌍 زلزال! ظهر {amount} {minerals}"}
        
        elif event_name == "قطيع ذئاب":
            damage = random.randint(3, 8)
            player.current_health = max(1, player.current_health - damage)
            return {"name": event_name, "message": f"🐺 هجوم ذئاب! خسرت {damage} صحة"}
        
        return {"name": event_name, "message": "حدث غامض"}
    
    # ============ نظام الأكل ============
    def eat_food(self, player: Player, food_name: str) -> Dict:
        """تناول الطعام"""
        food_values = {
            "apple": 4, "bread": 5, "cooked_beef": 8, "tropical_fruit": 8,
            "honey": 6, "golden_apple": 4, "raw_beef": 2, "raw_chicken": 1,
            "raw_pork": 2, "raw_mutton": 2, "milk": 3, "egg": 1,
            "cookie": 2, "cake": 7, "bear_meat": 6
        }
        
        if food_name not in food_values:
            return {"error": "هذا الطعام غير معروف"}
        
        # البحث عن الطعام في المخزون
        if not CraftingSystem.has_items(player, food_name, 1):
            return {"error": "ليس لديك هذا الطعام"}
        
        # استهلاك الطعام
        CraftingSystem.remove_items(player, food_name, 1)
        
        # زيادة الشبع
        food_value = food_values[food_name]
        player.current_hunger = min(player.max_hunger, player.current_hunger + food_value)
        
        # تأثيرات خاصة
        effects = []
        if food_name == "golden_apple":
            player.current_health = min(player.max_health, player.current_health + 4)
            effects.append("💛 استعدت 4 قلوب")
        elif food_name == "tropical_fruit":
            effects.append("🥭 شبع مضاعف!")
        elif food_name == "honey":
            effects.append("🍯 شفاء سريع!")
        
        # الأطعمة النيئة قد تسبب تسمم
        if "raw" in food_name and random.random() < 0.3:
            player.status_effects.append({"name": "food_poisoning", "duration": 3})
            effects.append("⚠️ تسمم غذائي! ستفقد صحة تدريجياً")
        
        self.session.commit()
        
        return {
            "food": food_name,
            "hunger_restored": food_value,
            "current_hunger": player.current_hunger,
            "effects": effects
        }
    
    # ============ نظام النوم ============
    def sleep_in_village(self, player: Player) -> Dict:
        """النوم في القرية"""
        if not player.can_sleep():
            hours_left = 12 - (datetime.utcnow() - player.last_sleep).seconds // 3600
            return {"error": f"لا يمكنك النوم الآن. انتظر {hours_left} ساعات"}
        
        # استعادة الصحة
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        
        # إزالة التأثيرات السلبية
        player.status_effects = [e for e in player.status_effects 
                               if e.get("name") not in ["poison", "food_poisoning"]]
        
        player.last_sleep = datetime.utcnow()
        self.session.commit()
        
        return {
            "message": "😴 نمت جيداً! تم استعادة صحتك وجوعك بالكامل",
            "health": player.current_health,
            "hunger": player.current_hunger
        }
    
    # ============ نظام المعبد ============
    def explore_temple(self, player: Player) -> Dict:
        """استكشاف المعبد - 5 غرف"""
        if player.level < 10:
            return {"error": "تحتاج مستوى 10 لدخول المعبد"}
        
        rooms = []
        survived = True
        puzzles_solved = 0
        
        # الغرفة 1: الأبواب
        correct_door = random.randint(1, 3)
        rooms.append({
            "room": 1,
            "name": "غرفة الأبواب",
            "description": "أمامك 3 أبواب، اختر الباب الصحيح (1-3)"
        })
        
        # الغرفة 2: الأشباح
        ghost_question = random.choice(["ما هو لون التفاح؟", "كم عدد الأرجل للعنكبوت؟"])
        ghost_answer = "أحمر" if "التفاح" in ghost_question else "8"
        rooms.append({
            "room": 2,
            "name": "غرفة الأشباح",
            "question": ghost_question
        })
        
        # الغرفة 3: اللهب
        rooms.append({
            "room": 3,
            "name": "غرفة اللهب",
            "description": "النار تلاحقك! اختر: (يمين/يسار/وسط)"
        })
        
        # الغرفة 4: الفخاخ
        rooms.append({
            "room": 4,
            "name": "غرفة الفخاخ",
            "description": "3 أزرار أمامك، واحد فقط آمن (1-3)"
        })
        
        # الغرفة 5: الكنز
        rooms.append({
            "room": 5,
            "name": "غرفة الكنز",
            "description": "3 صناديق، واحد فقط فيه الجوهرة (1-3)"
        })
        
        return {
            "temple": "المعبد الغامض",
            "rooms": rooms,
            "current_room": 1,
            "message": "🏛️ دخلت المعبد! أمامك 5 غرف مليئة بالتحديات"
        }
    
    def solve_temple_puzzle(self, player: Player, room: int, answer: str) -> Dict:
        """حل لغز في المعبد"""
        if room == 1:
            correct = random.randint(1, 3)
            if int(answer) == correct:
                return {"success": True, "message": "✅ الباب الصحيح! تقدم للغرفة التالية"}
            else:
                player.current_health = max(1, player.current_health - 5)
                return {"success": False, "message": "❌ باب خاطئ! خسرت 5 صحة"}
        
        elif room == 2:
            if answer.strip() in ["أحمر", "8"]:
                return {"success": True, "message": "✅ أجبت بشكل صحيح! الأشباح راضية"}
            else:
                player.current_health = max(1, player.current_health - 3)
                return {"success": False, "message": "❌ إجابة خاطئة! الأشباح غاضبة"}
        
        elif room == 3:
            correct = random.choice(["يمين", "يسار", "وسط"])
            if answer == correct:
                return {"success": True, "message": "✅ نجوت من النار!"}
            else:
                player.current_health = max(1, player.current_health - 8)
                return {"success": False, "message": "🔥 احترقت! خسرت 8 صحة"}
        
        elif room == 4:
            correct = random.randint(1, 3)
            if int(answer) == correct:
                return {"success": True, "message": "✅ الزر الآمن! تجنبت الفخ"}
            else:
                player.current_health = max(1, player.current_health - 6)
                return {"success": False, "message": "💥 فخ! خسرت 6 صحة"}
        
        elif room == 5:
            correct = random.randint(1, 3)
            if int(answer) == correct:
                # مكافأة الجوهرة
                gems = ["جوهرة القوة", "جوهرة السرعة", "جوهرة الحماية", "جوهرة الثروة", "جوهرة النار"]
                gem = random.choice(gems)
                player.inventory[f"slot_{random.randint(0,35)}"] = {"name": gem, "amount": 1}
                player.add_xp(30)
                
                if "القوة" in gem:
                    player.strength = min(100, player.strength + 5)
                elif "السرعة" in gem:
                    player.speed = min(100, player.speed + 5)
                elif "الحماية" in gem:
                    player.endurance = min(100, player.endurance + 5)
                elif "الثروة" in gem:
                    player.luck = min(100, player.luck + 5)
                elif "النار" in gem:
                    # تأثير ناري للسيف
                    pass
                
                return {
                    "success": True,
                    "gem": gem,
                    "message": f"🎉 رائع! حصلت على {gem}",
                    "temple_complete": True
                }
            else:
                return {"success": False, "message": "📦 صندوق فارغ! حاول مرة أخرى"}
        
        return {"error": "غرفة غير معروفة"}
    
    # ============ معركة التنين (الإندر) ============
    def start_dragon_fight(self, player: Player) -> Dict:
        """بدء معركة التنين بـ 5 مراحل"""
        if not player.inventory_has("ender_sword"):
            return {"error": "تحتاج سيف الإندر لمواجهة التنين"}
        
        if player.current_health < 15:
            return {"error": "صحتك منخفضة جداً لمواجهة التنين"}
        
        return {
            "boss": "تنين الإندر 🐉",
            "phase": 1,
            "total_phases": 5,
            "phase_name": "تدمير البلورات",
            "description": "أمامك 6 بلورات، كل بلورة محمية. اختر مكان الضربة (1-4)",
            "crystals_remaining": 6
        }
    
    def dragon_fight_phase(self, player: Player, phase: int, choice: str) -> Dict:
        """تنفيذ مرحلة من معركة التنين"""
        if phase == 1:
            # تدمير البلورات
            correct = random.randint(1, 4)
            if int(choice) == correct:
                crystals_destroyed = getattr(player, 'dragon_crystals', 6)
                crystals_destroyed -= 1
                player.dragon_crystals = crystals_destroyed
                
                if crystals_destroyed <= 0:
                    return {
                        "success": True,
                        "phase_complete": True,
                        "message": "🎯 دمرت كل البلورات! التنين يطير عالياً",
                        "next_phase": 2
                    }
                
                return {
                    "success": True,
                    "crystals_remaining": crystals_destroyed,
                    "message": f"💎 دمرت بلورة! تبقى {crystals_destroyed}"
                }
            else:
                player.current_health = max(1, player.current_health - 3)
                return {
                    "success": False,
                    "message": "❌ أخطأت! التنين يدافع عن البلورة"
                }
        
        elif phase == 2:
            # الرماية على التنين
            correct = random.choice(["يمين", "يسار", "فوق"])
            if choice == correct:
                return {
                    "success": True,
                    "phase_complete": True,
                    "message": "🏹 أصبت التنين! إنه ينزل للأرض",
                    "next_phase": 3
                }
            else:
                player.current_health = max(1, player.current_health - 5)
                return {
                    "success": False,
                    "message": "❌ أخطأت! التنين يهاجمك"
                }
        
        elif phase == 3:
            # هجوم السيف - 4 جولات
            if hasattr(player, 'dragon_sword_hits'):
                player.dragon_sword_hits += 1
            else:
                player.dragon_sword_hits = 1
            
            damages = {"رأس": 10, "جناح": 8, "ذيل": 5, "رجل": 7}
            damage = damages.get(choice, 3)
            
            if player.dragon_sword_hits >= 4:
                return {
                    "success": True,
                    "phase_complete": True,
                    "damage_dealt": damage,
                    "message": "⚔️ ضربات متتالية! التنين يغضب",
                    "next_phase": 4
                }
            
            return {
                "success": True,
                "damage_dealt": damage,
                "hits": player.dragon_sword_hits,
                "message": f"⚔️ ضربة {choice}! ضرر {damage}"
            }
        
        elif phase == 4:
            # الدفاع ضد الكرات النارية
            defenses = {"درع ناري": 100, "درع حديدي": 60, "درع خشبي": 20}
            protection = defenses.get(choice, 0)
            
            fire_damage = int(15 * (1 - protection / 100))
            player.current_health = max(1, player.current_health - fire_damage)
            
            return {
                "success": True,
                "phase_complete": True,
                "protection": protection,
                "damage_taken": fire_damage,
                "message": f"🛡️ {choice} يحميك {protection}%! تلقيت {fire_damage} ضرر",
                "next_phase": 5
            }
        
        elif phase == 5:
            # الضربة النهائية - 3 ضربات دقيقة
            if hasattr(player, 'final_blows'):
                player.final_blows += 1
            else:
                player.final_blows = 1
            
            if random.random() < 0.4:  # 40% نجاح
                if player.final_blows >= 3:
                    # النصر!
                    player.defeated_ender_dragon = True
                    player.add_xp(100)
                    CraftingSystem.add_item(player, "dragon_egg", 1)
                    
                    if "بطل الإندر" not in player.titles:
                        player.titles.append("بطل الإندر")
                    
                    # تنظيف
                    player.dragon_crystals = 6
                    player.dragon_sword_hits = 0
                    player.final_blows = 0
                    
                    return {
                        "success": True,
                        "victory": True,
                        "message": "🎉🎊 لقد هزمت تنين الإندر! أنت بطل الإندر!",
                        "rewards": ["بيضة التنين 🐉", "100 نقطة خبرة", "لقب بطل الإندر"]
                    }
                
                return {
                    "success": True,
                    "blow": player.final_blows,
                    "message": f"⚡ ضربة ناجحة {player.final_blows}/3"
                }
            else:
                damage = int(15 * (1 / player.final_blows))
                player.current_health = max(1, player.current_health - damage)
                return {
                    "success": False,
                    "damage_taken": damage,
                    "message": f"💥 أخطأت! التنين يعكس {damage} ضرر"
                }
        
        return {"error": "مرحلة غير معروفة"}
    
    # ============ الأحداث العالمية ============
    def trigger_world_event(self) -> Dict:
        """تفعيل حدث عالمي"""
        events = [
            {"name": "مطر الذهب", "emoji": "🌟", "effect": "gold_bonus", "duration": 1},
            {"name": "غزو الزومبي", "emoji": "🧟", "effect": "more_enemies", "duration": 1},
            {"name": "اكتمال القمر", "emoji": "🌕", "effect": "stronger_enemies", "duration": 1},
            {"name": "الشفق القطبي", "emoji": "🌌", "effect": "faster_explore", "duration": 2},
            {"name": "كسوف الشمس", "emoji": "🌑", "effect": "weaker_enemies", "duration": 1.5},
        ]
        
        event_data = random.choice(events)
        
        # إنشاء حدث عالمي في القاعدة
        world_event = WorldEvent(
            event_type=event_data["name"],
            end_time=datetime.utcnow() + timedelta(hours=event_data["duration"]),
            active=True
        )
        
        self.session.add(world_event)
        self.session.commit()
        
        return {
            "event": event_data["name"],
            "emoji": event_data["emoji"],
            "duration": event_data["duration"],
            "message": f"{event_data['emoji']} حدث عالمي: {event_data['name']}!"
        }
    
    def get_active_events(self) -> List[Dict]:
        """الحصول على الأحداث النشطة"""
        now = datetime.utcnow()
        active_events = self.session.query(WorldEvent).filter(
            WorldEvent.active == True,
            WorldEvent.end_time > now
        ).all()
        
        return [{
            "type": event.event_type,
            "remaining": str(event.end_time - now)
        } for event in active_events]
