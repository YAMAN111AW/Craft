import random
from datetime import datetime, timedelta
from database import Player, Session
from world_data import WorldData
from crafting_system import CraftingSystem

class GameMechanics:
    def __init__(self, session: Session):
        self.session = session
    
    def explore(self, player: Player, area_name: str) -> dict:
        area = WorldData.get_area(area_name)
        if not area:
            return {"error": "منطقة غير موجودة"}
        if player.level < area.level_req:
            return {"error": f"تحتاج مستوى {area.level_req}"}
        
        # Time calculation
        et = area.explore_time * (1 - player.speed * 0.005)
        if player.has_item("saddle"): et *= 0.5
        if player.has_item("compass"): et *= 0.8
        if player.has_item("elytra"): et *= 0.5
        
        # Hunger cost
        hunger = max(1, int(et / 25))
        player.current_hunger = max(0, player.current_hunger - hunger)
        
        # Gather resources
        rewards = []
        for _ in range(random.randint(3, 6)):
            r = WorldData.roll_resource(area, player.luck)
            amt = random.randint(r.min_amount, r.max_amount)
            player.add_item(r.name, amt)
            rewards.append(f"{r.emoji} {r.name} x{amt}")
        
        # Enemy encounter
        enemy_result = None
        enemy = WorldData.roll_enemy(area)
        if enemy:
            enemy_result = self.battle(player, enemy)
        
        # Random event
        event_result = None
        if area.events and random.random() < 0.25:
            ev = random.choice(area.events)
            event_result = self.handle_event(player, ev)
        
        # XP
        xp = random.randint(5, 15) + player.luck
        player.add_xp(xp)
        
        # Starvation check
        starve_msg = None
        if player.current_hunger <= 0:
            player.current_health = max(1, player.current_health - 3)
            starve_msg = "⚠️ أنت تتضور جوعاً!"
        
        player.last_action = datetime.utcnow()
        player.current_area = area_name
        self.session.commit()
        
        return {
            "area": area.name, "emoji": area.emoji, "time": int(et),
            "rewards": rewards, "enemy": enemy_result, "event": event_result,
            "xp": xp, "hunger": player.current_hunger, "health": player.current_health,
            "starve": starve_msg
        }
    
    def battle(self, player: Player, enemy) -> dict:
        p_dmg = self.calc_damage(player)
        p_def = self.calc_defense(player)
        
        # Pet bonus
        if player.pet == "wolf":
            p_dmg += 3
        
        php = player.current_health
        ehp = enemy.health
        rounds = []
        escaped = False
        
        for rnd in range(1, 6):
            # Player attack
            atk = max(1, p_dmg - random.randint(0, 3))
            ehp -= atk
            
            if ehp <= 0:
                rounds.append({"r":rnd, "patk":atk, "win":True})
                break
            
            # Enemy attack
            eatk = max(1, enemy.damage - p_def//3)
            if enemy.special == "explode" and rnd >= 3:
                eatk *= 2
                rounds.append({"r":rnd, "patk":atk, "eatk":eatk, "sp":"💥 انفجار!"})
            elif enemy.special == "steal" and random.random() < 0.3:
                # Steal random item
                inv = player.get_inv()
                items = [s for s in inv.values() if s]
                if items:
                    stolen = random.choice(items)
                    stolen["amount"] = max(1, stolen["amount"]-1)
                    rounds.append({"r":rnd, "patk":atk, "eatk":eatk, "sp":f"🪲 سرق {stolen['name']}!"})
                else:
                    rounds.append({"r":rnd, "patk":atk, "eatk":eatk})
            else:
                rounds.append({"r":rnd, "patk":atk, "eatk":eatk})
            
            php -= eatk
            if php <= 0:
                break
            
            # Tame wolf
            if enemy.special == "tameable" and random.random() < 0.15:
                player.pet = "wolf"
                escaped = True
                rounds.append({"r":rnd, "tame":"🐺 تم ترويض الذئب!"})
                break
            
            if random.random() < 0.2 and rnd >= 2:
                escaped = True
                break
        
        old_hp = player.current_health
        player.current_health = max(1, php)
        
        result = {"name":enemy.name, "emoji":enemy.emoji, "rounds":rounds, "escaped":escaped}
        
        if ehp <= 0:
            player.add_xp(enemy.xp)
            drops = []
            for item, amt, prob in enemy.drops:
                if random.random() < prob:
                    player.add_item(item, amt)
                    drops.append(f"{item} x{amt}")
            result["win"] = True
            result["xp"] = enemy.xp
            result["drops"] = drops
        else:
            result["win"] = False
            result["hp_lost"] = old_hp - player.current_health
        
        return result
    
    def calc_damage(self, player):
        dmg = 2
        eq = player.get_equip()
        w = eq.get("weapon")
        weapon_dmg = {"wooden_sword":4,"stone_sword":5,"iron_sword":6,"diamond_sword":7,"ender_sword":10}
        if w in weapon_dmg:
            dmg += weapon_dmg[w]
        return dmg + int(dmg * player.strength * 0.02)
    
    def calc_defense(self, player):
        defense = 0
        eq = player.get_equip()
        for slot in ["helmet","chestplate","leggings","boots"]:
            armor = eq.get(slot)
            if armor:
                if "diamond" in str(armor): defense += 3
                elif "iron" in str(armor): defense += 2
                elif "fire" in str(armor): defense += 4
        return defense
    
    def handle_event(self, player, ev):
        eff = ev["eff"]
        if eff == "gold":
            player.add_item("gold_ore", random.randint(3, 8))
        elif eff == "minerals":
            ores = ["iron_ore","gold_ore","coal"]
            player.add_item(random.choice(ores), random.randint(2, 5))
        elif eff == "wolf_attack":
            dmg = random.randint(5, 12)
            player.current_health = max(1, player.current_health - dmg)
            return {"name":ev["name"], "msg":f"{ev['msg']} خسرت {dmg} صحة"}
        elif eff == "chest_basic":
            player.add_item("bread", 2)
            player.add_item("wooden_sword", 1)
        elif eff == "chest_iron":
            player.add_item("gold_ore", 3)
            player.add_item("iron_pickaxe", 1)
        elif eff == "chest_rare":
            player.add_item("diamond", 1)
            player.add_item("golden_apple", 1)
        elif eff == "ender_ship":
            player.add_item("elytra", 1)
        return {"name":ev["name"], "msg":ev["msg"]}
    
    def eat(self, player, food):
        food_db = {
            "apple":4,"bread":5,"cooked_beef":8,"tropical_fruit":8,
            "honey":6,"golden_apple":4,"milk":3,"egg":1,
            "raw_beef":2,"raw_chicken":1,"raw_pork":2,"raw_mutton":2
        }
        if food not in food_db:
            return {"error":"طعام غير معروف"}
        if not player.has_item(food):
            return {"error":"لا تملك هذا الطعام"}
        
        player.remove_item(food)
        val = food_db[food]
        player.current_hunger = min(player.max_hunger, player.current_hunger + val)
        
        effects = []
        if food == "golden_apple":
            player.current_health = min(player.max_health, player.current_health + 4)
            effects.append("💛 +4 صحة")
        if "raw" in food and random.random() < 0.3:
            effects.append("⚠️ تسمم غذائي!")
        
        self.session.commit()
        return {"food":food,"hunger":val,"current":player.current_hunger,"effects":effects}
    
    def sleep(self, player):
        if not player.can_sleep():
            left = 12 - (datetime.utcnow() - player.last_sleep).seconds // 3600
            return {"error":f"انتظر {left} ساعات"}
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        player.last_sleep = datetime.utcnow()
        self.session.commit()
        return {"msg":"😴 نمت جيداً!","hp":player.current_health,"hunger":player.current_hunger}
    
    def temple(self, player):
        if player.level < 10:
            return {"error":"تحتاج مستوى 10"}
        return {
            "msg":"🏛️ دخلت المعبد! 5 غرف بانتظارك",
            "rooms":[
                {"r":1,"name":"الأبواب","desc":"اختر باب (1-3)"},
                {"r":2,"name":"الأشباح","q":"كم عدد ألوان قوس قزح؟","a":"7"},
                {"r":3,"name":"اللهب","desc":"اختر طريق (يمين/يسار/وسط)"},
                {"r":4,"name":"الفخاخ","desc":"اختر زر آمن (1-3)"},
                {"r":5,"name":"الكنز","desc":"اختر صندوق (1-3)"},
            ]
        }
    
    def solve_temple(self, player, room, answer):
        if room == 1:
            ok = str(answer) == str(random.randint(1,3))
            dmg = 5
        elif room == 2:
            ok = answer.strip() in ["7","سبعة"]
            dmg = 3
        elif room == 3:
            ok = answer in ["يمين","يسار","وسط"] and answer == random.choice(["يمين","يسار","وسط"])
            dmg = 8
        elif room == 4:
            ok = str(answer) == str(random.randint(1,3))
            dmg = 6
        elif room == 5:
            ok = str(answer) == str(random.randint(1,3))
            if ok:
                gems = ["جوهرة القوة","جوهرة السرعة","جوهرة الحماية","جوهرة الثروة","جوهرة النار"]
                gem = random.choice(gems)
                player.add_item(gem, 1)
                player.add_xp(30)
                if "قوة" in gem: player.strength = min(100, player.strength+5)
                elif "سرعة" in gem: player.speed = min(100, player.speed+5)
                elif "حماية" in gem: player.endurance = min(100, player.endurance+5)
                elif "ثروة" in gem: player.luck = min(100, player.luck+5)
                self.session.commit()
                return {"win":True,"gem":gem,"msg":f"🎉 حصلت على {gem}!"}
            return {"win":False,"msg":"📦 صندوق فارغ!"}
        else:
            return {"error":"غرفة غير معروفة"}
        
        if not ok:
            player.current_health = max(1, player.current_health - dmg)
            self.session.commit()
            return {"win":False,"msg":f"❌ خطأ! -{dmg} صحة"}
        return {"win":True,"msg":"✅ صحيح!","next":room+1}
