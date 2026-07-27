import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from database import Player, WorldEvent, Session, get_or_create_player
from world_data import WorldData, Area, Enemy, Resource

class GameMechanics:
    def __init__(self, session: Session):
        self.session = session
        self.world_data = WorldData()
    
    def explore_area(self, player: Player, area_name: str) -> Dict:
        """استكشاف منطقة جديدة"""
        try:
            area = self.world_data.get_area(area_name)
            if not area:
                return {"error": "المنطقة غير موجودة"}
            
            if player.level < area.level_required:
                return {"error": f"تحتاج مستوى {area.level_required} لدخول هذه المنطقة"}
            
            # حساب وقت الاستكشاف
            explore_time = area.exploration_time
            explore_time *= (1 - player.speed * 0.005)
            
            # تأثير المعدات
            if player.has_item("compass"):
                explore_time *= 0.8
            if player.has_item("saddle"):
                explore_time *= 0.5
            if player.has_item("elytra"):
                explore_time *= 0.5
            
            # تقليل الجوع
            hunger_cost = max(1, int(explore_time / 30))
            player.current_hunger = max(0, player.current_hunger - hunger_cost)
            
            # جمع الموارد
            num_resources = random.randint(3, 5)
            rewards = []
            for _ in range(num_resources):
                resource = self.world_data.get_random_resource(area, player.luck)
                if resource:
                    amount = random.randint(resource.min_amount, resource.max_amount)
                    player.add_item(resource.name, amount)
                    rewards.append(f"{resource.emoji} {resource.name} x{amount}")
            
            # مواجهة الأعداء (30% فرصة)
            enemy_result = None
            if random.random() < 0.3:
                enemy = self.world_data.get_random_enemy(area)
                if enemy:
                    enemy_result = self.fight_enemy(player, enemy)
            
            # حدث عشوائي (25% فرصة)
            event_result = None
            if random.random() < 0.25 and area.random_events:
                event_result = self.trigger_random_event(player, area)
            
            # حساب الخبرة
            xp_gained = random.randint(5, 15) + int(player.luck * 0.2)
            player.add_xp(xp_gained)
            
            # تحديث آخر نشاط
            player.last_action = datetime.utcnow()
            player.current_area = area_name
            
            # التحقق من الجوع الحاد
            starvation_msg = None
            if player.current_hunger <= 0:
                player.current_health = max(1, player.current_health - 3)
                starvation_msg = "⚠️ أنت تتضور جوعاً! صحتك تنخفض"
            
            self.session.commit()
            
            result = {
                "area": area.name,
                "emoji": area.emoji,
                "explore_time": int(explore_time),
                "rewards": rewards,
                "enemy": enemy_result,
                "event": event_result,
                "xp_gained": xp_gained,
                "hunger_cost": hunger_cost,
                "current_hunger": player.current_hunger,
                "current_health": player.current_health,
                "starvation": starvation_msg
            }
            
            return result
            
        except Exception as e:
            self.session.rollback()
            return {"error": f"حدث خطأ: {str(e)}"}
    
    def fight_enemy(self, player: Player, enemy: Enemy) -> Dict:
        """نظام قتال مبسط"""
        try:
            player_damage = self.calculate_player_damage(player)
            player_defense = self.calculate_player_defense(player)
            
            rounds = []
            player_hp = player.current_health
            enemy_hp = enemy.health
            escaped = False
            
            for round_num in range(1, 6):
                round_result = {"round": round_num}
                
                # دور اللاعب
                player_attack = max(1, player_damage - random.randint(0, 2))
                enemy_hp -= player_attack
                round_result["player_attack"] = player_attack
                
                if enemy_hp <= 0:
                    round_result["victory"] = True
                    rounds.append(round_result)
                    break
                
                # دور العدو
                enemy_attack = max(1, enemy.damage - player_defense // 3)
                player_hp -= enemy_attack
                round_result["enemy_attack"] = enemy_attack
                
                rounds.append(round_result)
                
                if player_hp <= 0:
                    break
                
                # فرصة هروب 20%
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
                xp_reward = enemy.xp_reward + int(player.luck * 0.3)
                player.add_xp(xp_reward)
                
                drops = []
                for item_name, amount, probability in enemy.drops:
                    if random.random() < probability * (1 + player.luck * 0.01):
                        player.add_item(item_name, amount)
                        drops.append(f"{item_name} x{amount}")
                
                result["victory"] = True
                result["xp_reward"] = xp_reward
                result["drops"] = drops
            else:
                result["victory"] = False
                result["health_lost"] = old_health - player.current_health
            
            return result
            
        except Exception as e:
            return {"error": f"خطأ في القتال: {str(e)}"}
    
    def calculate_player_damage(self, player: Player) -> int:
        """حساب ضرر اللاعب"""
        base_damage = 2
        
        # التحقق من السلاح المجهز
        equip = player.get_equipment()
        weapon = equip.get("weapon")
        
        if weapon:
            weapon_damages = {
                "wooden_sword": 4, "stone_sword": 5, "iron_sword": 6,
                "diamond_sword": 7, "ender_sword": 10
            }
            base_damage += weapon_damages.get(weapon, 3)
        
        # إضافة القوة
        base_damage += int(base_damage * player.strength * 0.02)
        
        return base_damage
    
    def calculate_player_defense(self, player: Player) -> int:
        """حساب دفاع اللاعب"""
        defense = 0
        equip = player.get_equipment()
        
        for slot in ["helmet", "chestplate", "leggings", "boots"]:
            armor = equip.get(slot)
            if armor:
                if "diamond" in str(armor):
                    defense += 3
                elif "iron" in str(armor):
                    defense += 2
                elif "fire" in str(armor):
                    defense += 4
        
        return defense
    
    def trigger_random_event(self, player: Player, area: Area) -> Dict:
        """تفعيل حدث عشوائي"""
        if not area.random_events:
            return {"name": "لا حدث"}
        
        event = random.choice(area.random_events)
        event_name = event["name"]
        
        if event_name == "عاصفة":
            return {"name": event_name, "message": "🌧️ عاصفة! زاد وقت الاستكشاف 50%"}
        
        elif event_name == "قوس قزح":
            gold_amount = random.randint(5, 15)
            player.add_item("gold_ingot", gold_amount)
            return {"name": event_name, "message": f"🌈 قوس قزح! حصلت على {gold_amount} سبائك ذهب"}
        
        elif event_name == "زلزال":
            minerals = random.choice(["iron_ore", "gold_ore", "coal"])
            amount = random.randint(2, 5)
            player.add_item(minerals, amount)
            return {"name": event_name, "message": f"🌍 زلزال! ظهر {amount} {minerals}"}
        
        elif event_name == "قطيع ذئاب":
            damage = random.randint(3, 8)
            player.current_health = max(1, player.current_health - damage)
            return {"name": event_name, "message": f"🐺 هجوم ذئاب! خسرت {damage} صحة"}
        
        return {"name": event_name, "message": "حدث غامض"}
    
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
        
        if not player.has_item(food_name, 1):
            return {"error": "ليس لديك هذا الطعام"}
        
        # استهلاك الطعام
        player.remove_item(food_name, 1)
        
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
        
        # الأطعمة النيئة قد تسبب تسمم
        if "raw" in food_name and random.random() < 0.3:
            effects_list = player.get_status_effects()
            effects_list.append({"name": "food_poisoning", "duration": 3})
            player.set_status_effects(effects_list)
            effects.append("⚠️ تسمم غذائي!")
        
        self.session.commit()
        
        return {
            "food": food_name,
            "hunger_restored": food_value,
            "current_hunger": player.current_hunger,
            "effects": effects
        }
    
    def sleep_in_village(self, player: Player) -> Dict:
        """النوم في القرية"""
        if not player.can_sleep():
            time_diff = datetime.utcnow() - player.last_sleep
            hours_left = 12 - (time_diff.total_seconds() / 3600)
            return {"error": f"لا يمكنك النوم الآن. انتظر {int(hours_left)} ساعات"}
        
        # استعادة الصحة والجوع
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        
        # إزالة التأثيرات السلبية
        effects = player.get_status_effects()
        effects = [e for e in effects if e.get("name") not in ["poison", "food_poisoning"]]
        player.set_status_effects(effects)
        
        player.last_sleep = datetime.utcnow()
        self.session.commit()
        
        return {
            "message": "😴 نمت جيداً! تم استعادة صحتك وجوعك بالكامل",
            "health": player.current_health,
            "hunger": player.current_hunger
        }

    def explore_temple(self, player: Player) -> Dict:
        """استكشاف المعبد"""
        if player.level < 10:
            return {"error": "تحتاج مستوى 10 لدخول المعبد"}
        
        rooms = []
        
        rooms.append({
            "room": 1,
            "name": "غرفة الأبواب",
            "description": "أمامك 3 أبواب، اختر الباب الصحيح (1-3)"
        })
        
        ghost_questions = [
            ("ما هو لون التفاح؟", "أحمر"),
            ("كم عدد الأرجل للعنكبوت؟", "8"),
            ("ما هو أقوى معدن؟", "ألماس")
        ]
        q, a = random.choice(ghost_questions)
        rooms.append({
            "room": 2,
            "name": "غرفة الأشباح",
            "question": q,
            "answer": a
        })
        
        rooms.append({
            "room": 3,
            "name": "غرفة اللهب",
            "description": "النار تلاحقك! اختر: (يمين/يسار/وسط)"
        })
        
        rooms.append({
            "room": 4,
            "name": "غرفة الفخاخ",
            "description": "3 أزرار أمامك، واحد فقط آمن (1-3)"
        })
        
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
        """حل لغز المعبد"""
        if room == 1:
            correct = random.randint(1, 3)
            if str(answer) == str(correct):
                return {"success": True, "message": "✅ الباب الصحيح! تقدم للغرفة التالية", "next_room": 2}
            else:
                player.current_health = max(1, player.current_health - 5)
                self.session.commit()
                return {"success": False, "message": "❌ باب خاطئ! خسرت 5 صحة"}
        
        elif room == 2:
            if answer.strip() in ["أحمر", "8", "ألماس"]:
                return {"success": True, "message": "✅ أجبت بشكل صحيح!", "next_room": 3}
            else:
                player.current_health = max(1, player.current_health - 3)
                self.session.commit()
                return {"success": False, "message": "❌ إجابة خاطئة!"}
        
        elif room == 3:
            correct = random.choice(["يمين", "يسار", "وسط"])
            if answer == correct:
                return {"success": True, "message": "✅ نجوت من النار!", "next_room": 4}
            else:
                player.current_health = max(1, player.current_health - 8)
                self.session.commit()
                return {"success": False, "message": "🔥 احترقت! خسرت 8 صحة"}
        
        elif room == 4:
            correct = random.randint(1, 3)
            if str(answer) == str(correct):
                return {"success": True, "message": "✅ الزر الآمن!", "next_room": 5}
            else:
                player.current_health = max(1, player.current_health - 6)
                self.session.commit()
                return {"success": False, "message": "💥 فخ! خسرت 6 صحة"}
        
        elif room == 5:
            correct = random.randint(1, 3)
            if str(answer) == str(correct):
                gems = ["جوهرة القوة", "جوهرة السرعة", "جوهرة الحماية", "جوهرة الثروة", "جوهرة النار"]
                gem = random.choice(gems)
                
                player.add_item(gem, 1)
                player.add_xp(30)
                
                if "القوة" in gem:
                    player.strength = min(100, player.strength + 5)
                elif "السرعة" in gem:
                    player.speed = min(100, player.speed + 5)
                elif "الحماية" in gem:
                    player.endurance = min(100, player.endurance + 5)
                elif "الثروة" in gem:
                    player.luck = min(100, player.luck + 5)
                
                self.session.commit()
                
                return {
                    "success": True,
                    "gem": gem,
                    "message": f"🎉 رائع! حصلت على {gem}",
                    "temple_complete": True
                }
            else:
                return {"success": False, "message": "📦 صندوق فارغ! حاول مرة أخرى"}
        
        return {"error": "غرفة غير معروفة"}
