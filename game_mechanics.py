import random, threading, time
from datetime import datetime, timedelta
from world_data import WorldData

class GameMechanics:
    def __init__(self, session):
        self.session = session
    
    def start_chopping(self, player, tree):
        player.is_exploring = True
        player.explore_end_time = None
        self.session.commit()
        
        return {
            "tree": tree,
            "total_blocks": tree.total_blocks,
            "blocks_left": tree.total_blocks,
            "animation": self.get_tree_animation(tree.total_blocks, tree.total_blocks)
        }
    
    def chop_block(self, player, tree, blocks_left):
        if blocks_left <= 0:
            return {"done": True, "msg": "الشجرة خلاص انكسرت"}
        
        blocks_left -= 1
        
        rewards = []
        for res, amt in tree.resources:
            player.add_item(res, amt)
            rewards.append(f"{res} x{amt}")
        
        if tree.rare_drop:
            rare_res, rare_amt, prob = tree.rare_drop
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"✨ {rare_res} x{rare_amt}")
        
        player.current_hunger = max(0, player.current_hunger - 0.5)
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 2)
        
        player.add_xp(1)
        self.session.commit()
        
        result = {
            "done": blocks_left <= 0,
            "blocks_left": blocks_left,
            "rewards": rewards,
            "animation": self.get_tree_animation(tree.total_blocks, blocks_left),
            "hunger": player.current_hunger,
            "health": player.current_health
        }
        
        if player.current_health <= 0:
            result["dead"] = True
            result["msg"] = "لقد مت من الجوع"
            self.respawn(player)
        
        return result
    
    def get_tree_animation(self, total, left):
        broken = total - left
        trunk = ""
        for i in range(total):
            if i < broken:
                trunk += "🟫"
            else:
                trunk += "🟩"
        
        leaves = "🌿" if left > 2 else "🍂" if left > 0 else ""
        
        animation = f"""
   {leaves}
    {leaves} {leaves}
     ||
   {trunk}
        """
        return animation
    
    def start_mining(self, player, rock):
        player.is_exploring = True
        player.explore_end_time = None
        self.session.commit()
        
        return {
            "rock": rock,
            "total_blocks": rock.total_blocks,
            "blocks_left": rock.total_blocks,
            "animation": self.get_rock_animation(rock.total_blocks, rock.total_blocks)
        }
    
    def mine_block(self, player, rock, blocks_left):
        if blocks_left <= 0:
            return {"done": True, "msg": "الحجر اتكسر كله"}
        
        blocks_left -= 1
        
        rewards = []
        for res, amt in rock.resources:
            player.add_item(res, amt)
            rewards.append(f"{res} x{amt}")
        
        if rock.rare_drop:
            rare_res, rare_amt, prob = rock.rare_drop
            if random.random() < prob:
                player.add_item(rare_res, rare_amt)
                rewards.append(f"💎 {rare_res} x{rare_amt}")
        
        player.current_hunger = max(0, player.current_hunger - 0.5)
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 2)
        
        player.add_xp(1)
        self.session.commit()
        
        result = {
            "done": blocks_left <= 0,
            "blocks_left": blocks_left,
            "rewards": rewards,
            "animation": self.get_rock_animation(rock.total_blocks, blocks_left),
            "hunger": player.current_hunger,
            "health": player.current_health
        }
        
        if player.current_health <= 0:
            result["dead"] = True
            result["msg"] = "لقد مت"
            self.respawn(player)
        
        return result
    
    def get_rock_animation(self, total, left):
        broken = total - left
        rock_line = ""
        for i in range(total):
            if i < broken:
                rock_line += "🪨"
            else:
                rock_line += "⬛"
        
        sparkles = "✨" if broken > 0 else ""
        
        animation = f"""
   {sparkles}
   {rock_line}
   ⛏️ اضرب
        """
        return animation
    
    def hunt_animal(self, player, animal_name):
        if animal_name not in WorldData.ANIMAL_LOOT:
            return {"error": "حيوان غير معروف"}
        
        loot = WorldData.ANIMAL_LOOT[animal_name]
        rewards = []
        for res, amt in loot:
            player.add_item(res, amt)
            rewards.append(f"{res} x{amt}")
        
        player.current_hunger = max(0, player.current_hunger - 1)
        player.add_xp(3)
        self.session.commit()
        
        return {"animal": animal_name, "rewards": rewards}
    
    def start_battle(self, player, enemy):
        return {
            "enemy": enemy,
            "enemy_hp": enemy.health,
            "player_hp": player.current_health,
            "max_enemy_hp": enemy.health,
            "round": 0,
            "log": [f"⚔️ بدأ القتال مع {enemy.emoji} {enemy.name}"]
        }
    
    def battle_action(self, player, enemy, enemy_hp, player_hp, action, log, round_num):
        p_dmg = self.calc_damage(player)
        p_def = self.calc_defense(player)
        
        if action == "attack":
            atk = max(1, p_dmg - random.randint(0, 3))
            enemy_hp -= atk
            log.append(f"🗡️ ضربت {enemy.name} -{atk} HP")
            
            if enemy_hp <= 0:
                player.add_xp(enemy.xp)
                drops = []
                for item, amt, prob in enemy.drops:
                    if random.random() < prob:
                        player.add_item(item, amt)
                        drops.append(f"{item} x{amt}")
                
                if enemy.special == "tameable" and random.random() < 0.2:
                    player.pet = "wolf"
                    log.append("🐺 تم ترويض الذئب")
                
                self.session.commit()
                return {"win": True, "enemy_hp": 0, "player_hp": player_hp, "log": log, "drops": drops, "xp": enemy.xp}
        
        elif action == "eat":
            if player.current_hunger < 20:
                player.current_hunger = min(20, player.current_hunger + 5)
                log.append("🍖 أكلت +5 شبع")
            else:
                log.append("🍖 أنت شبعان")
        
        elif action == "run":
            if random.random() < 0.5:
                log.append("🏃 هربت بنجاح")
                self.session.commit()
                return {"escaped": True, "log": log}
            else:
                log.append("🏃 فشلت في الهروب")
        
        # دور العدو
        if enemy_hp > 0:
            eatk = max(1, enemy.damage - p_def // 3)
            if enemy.special == "explode" and round_num >= 3:
                eatk *= 2
                log.append(f"💥 {enemy.name} انفجر -{eatk} HP")
            elif enemy.special == "steal" and random.random() < 0.3:
                inv = player.get_inv()
                items = [s for s in inv.values() if s]
                if items:
                    stolen = random.choice(items)
                    stolen["amount"] = max(1, stolen["amount"] - 1)
                    log.append(f"🪲 سرق {stolen['name']}")
            else:
                log.append(f"💢 {enemy.name} ضربك -{eatk} HP")
            
            player_hp -= eatk
        
        player.current_health = max(0, player_hp)
        self.session.commit()
        
        if player_hp <= 0:
            log.append("💀 لقد مت")
            self.respawn(player)
            return {"dead": True, "log": log}
        
        return {"enemy_hp": enemy_hp, "player_hp": player_hp, "log": log, "round": round_num + 1}
    
    def calc_damage(self, player):
        dmg = 2
        eq = player.get_equip()
        w = eq.get("weapon")
        weapon_dmg = {"wooden_sword":4,"stone_sword":5,"iron_sword":6,"diamond_sword":7,"ender_sword":10}
        if w in weapon_dmg:
            dmg += weapon_dmg[w]
        if player.pet == "wolf":
            dmg += 3
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
    
    def respawn(self, player):
        player.current_health = player.max_health // 2
        player.current_hunger = 10
        player.current_area = "forest"
        player.is_exploring = False
        player.game_time = 0
        self.session.commit()
    
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
        if "raw" in food and random.random() < 0.3:
            effects.append("تسمم غذائي")
        
        self.session.commit()
        return {"food":food,"hunger":val,"current":player.current_hunger,"effects":effects}
    
    def sleep(self, player):
        if not player.can_sleep():
            left = 12 - (datetime.utcnow() - player.last_sleep).seconds // 3600
            return {"error":f"انتظر {left} ساعات"}
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        player.last_sleep = datetime.utcnow()
        player.game_time = 0
        self.session.commit()
        return {"msg":"نمت جيدا","hp":player.current_health,"hunger":player.current_hunger}
    
    def advance_game_time(self, player, minutes=10):
        player.game_time = (player.game_time + minutes) % 240
        self.session.commit()
        return player.is_night()
