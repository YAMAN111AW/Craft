import random, threading, time
from datetime import datetime, timedelta
from world_data import WorldData

class GameMechanics:
    def __init__(self, session):
        self.session = session
    
    def update_game_time(self, player):
        """تحديث الوقت بناءً على آخر نشاط للاعب"""
        if player.last_action:
            minutes_passed = (datetime.utcnow() - player.last_action).total_seconds() / 60
            if minutes_passed > 5:
                steps = int(minutes_passed / 5)
                for _ in range(min(steps, 10)):
                    player.advance_time(5)
        player.last_action = datetime.utcnow()
        self.session.commit()
        return player.get_time_of_day()
    
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
        
        # استنزاف الجوع مع تأثير الوقت
        hunger_cost = 0.5
        if player.is_night():
            hunger_cost = 0.8  # أكثر جوع في الليل
        
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 2)
        
        # مكافأة خبرة حسب الوقت
        xp_reward = 1
        if player.is_night():
            xp_reward = 2  # خبرة مضاعفة في الليل
        
        player.add_xp(xp_reward)
        
        result = {
            "done": blocks_left <= 0,
            "blocks_left": blocks_left,
            "rewards": rewards,
            "animation": self.get_tree_animation(tree.total_blocks, blocks_left),
            "hunger": player.current_hunger,
            "health": player.current_health,
            "xp": xp_reward
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
        
        # استنزاف الجوع
        hunger_cost = 0.5
        if player.is_night():
            hunger_cost = 0.8
        
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        if player.current_hunger <= 0:
            player.current_health = max(0, player.current_health - 2)
        
        xp_reward = 1
        if player.is_night():
            xp_reward = 2
        
        player.add_xp(xp_reward)
        
        result = {
            "done": blocks_left <= 0,
            "blocks_left": blocks_left,
            "rewards": rewards,
            "animation": self.get_rock_animation(rock.total_blocks, blocks_left),
            "hunger": player.current_hunger,
            "health": player.current_health,
            "xp": xp_reward
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
            # مكافأة إضافية حسب الوقت
            bonus = 0
            if not player.is_night():
                bonus = random.randint(0, 1)  # نهار = موارد أكثر
            player.add_item(res, amt + bonus)
            rewards.append(f"{res} x{amt + bonus}")
        
        hunger_cost = 1
        if player.is_night():
            hunger_cost = 1.5
        
        player.current_hunger = max(0, player.current_hunger - hunger_cost)
        xp_reward = 3
        if player.is_night():
            xp_reward = 5
        
        player.add_xp(xp_reward)
        self.session.commit()
        
        return {"animal": animal_name, "rewards": rewards}
    
    def calc_damage(self, player):
        dmg = 2
        eq = player.get_equip()
        w = eq.get("weapon")
        weapon_dmg = {
            "wooden_sword": 4, "stone_sword": 6,
            "iron_sword": 8, "diamond_sword": 10,
            "ender_sword": 14
        }
        if w in weapon_dmg:
            dmg += weapon_dmg[w]
        if player.pet == "wolf":
            dmg += 3
        # تأثير الوقت (الليل = قوة أقل)
        if player.is_night():
            dmg = int(dmg * 0.9)
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
        # تأثير الوقت (الليل = دفاع أقل)
        if player.is_night():
            defense = int(defense * 0.8)
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
            "apple": 4, "bread": 5, "cooked_beef": 8, "tropical_fruit": 8,
            "honey": 6, "golden_apple": 4, "milk": 3, "egg": 1,
            "raw_beef": 2, "raw_chicken": 1, "raw_pork": 2, "raw_mutton": 2
        }
        if food not in food_db:
            return {"error":"طعام غير معروف"}
        if not player.has_item(food):
            return {"error":"لا تملك هذا الطعام"}
        
        player.remove_item(food)
        val = food_db[food]
        # تأثير الوقت (الليل = أكل أقل فائدة)
        if player.is_night():
            val = int(val * 0.8)
        
        player.current_hunger = min(player.max_hunger, player.current_hunger + val)
        
        effects = []
        if food == "golden_apple":
            player.current_health = min(player.max_health, player.current_health + 4)
        if "raw" in food and random.random() < 0.3:
            effects.append("تسمم غذائي")
            player.current_health = max(0, player.current_health - 2)
        
        self.session.commit()
        return {"food":food,"hunger":val,"current":player.current_hunger,"effects":effects}
    
    def sleep(self, player):
        if not player.can_sleep():
            left = 12 - (datetime.utcnow() - player.last_sleep).seconds // 3600
            return {"error":f"انتظر {left} ساعات"}
        player.current_health = player.max_health
        player.current_hunger = player.max_hunger
        player.last_sleep = datetime.utcnow()
        player.game_time = 0  # يستيقظ فجراً
        self.session.commit()
        return {"msg":"نمت جيدا","hp":player.current_health,"hunger":player.current_hunger}
    
    def advance_game_time(self, player, minutes=10):
        player.game_time = (player.game_time + minutes) % 240
        self.session.commit()
        return player.is_night()


# ===== نظام القتال الجديد =====
class BattleSystem:
    """نظام قتال متقدم"""
    
    def __init__(self, session):
        self.session = session
    
    def start_battle(self, player, enemy):
        """بدء معركة جديدة"""
        battle_data = {
            'player_hp': player.current_health,
            'player_max_hp': player.max_health,
            'enemy_hp': enemy.health,
            'enemy_max_hp': enemy.health,
            'enemy': enemy,
            'round': 0,
            'log': [],
            'player_buffs': {'shield': 0, 'strength': 0, 'regeneration': 0},
            'enemy_buffs': {'shield': 0},
            'last_player_action': None,
            'player_defending': False,
            'is_night': player.is_night(),
        }
        battle_data['log'].append(f"⚔️ بدأ القتال مع {enemy.emoji} {enemy.name}!")
        if player.is_night():
            battle_data['log'].append("🌙 القتال في الليل!")
        return battle_data
    
    def player_attack(self, player, battle_data):
        """هجوم اللاعب"""
        enemy = battle_data['enemy']
        enemy_hp = battle_data['enemy_hp']
        
        # حساب الضرر
        base_damage = 2
        eq = player.get_equip()
        weapon = eq.get('weapon')
        
        weapon_damage = {
            None: 1,
            'wooden_sword': 4, 'stone_sword': 6,
            'iron_sword': 8, 'diamond_sword': 10,
            'ender_sword': 14
        }
        base_damage += weapon_damage.get(weapon, 2)
        
        # تأثير القوة
        base_damage += player.strength // 3
        
        # تأثير البافات
        base_damage += battle_data['player_buffs']['strength']
        
        # تأثير الوقت
        if battle_data['is_night']:
            base_damage = int(base_damage * 0.8)  # ضرر أقل في الليل
        
        # تضارب (critical hit)
        if random.random() < 0.15 + (player.luck / 100):
            base_damage *= 2
            battle_data['log'].append("💥 ضربة حاسمة!")
        
        # دفاع العدو
        enemy_defense = 0
        if battle_data['enemy_buffs']['shield'] > 0:
            enemy_defense = battle_data['enemy_buffs']['shield']
            battle_data['enemy_buffs']['shield'] = max(0, battle_data['enemy_buffs']['shield'] - 2)
        
        final_damage = max(1, base_damage - enemy_defense)
        enemy_hp = max(0, enemy_hp - final_damage)
        
        battle_data['enemy_hp'] = enemy_hp
        battle_data['log'].append(f"🗡️ ضربت {enemy.name} بـ {final_damage} ضرر")
        battle_data['player_defending'] = False
        battle_data['last_player_action'] = 'attack'
        
        return battle_data
    
    def player_defend(self, player, battle_data):
        """دفاع اللاعب"""
        shield_amount = 3
        if battle_data['is_night']:
            shield_amount = 2  # دفاع أقل في الليل
        
        battle_data['player_defending'] = True
        battle_data['player_buffs']['shield'] += shield_amount
        battle_data['log'].append(f"🛡️ استعديت للدفاع (+{shield_amount} درع)")
        battle_data['last_player_action'] = 'defend'
        return battle_data
    
    def enemy_turn(self, player, battle_data):
        """دور العدو"""
        enemy = battle_data['enemy']
        player_hp = battle_data['player_hp']
        
        # هل اللاعب مدافع؟
        player_defense = 0
        if battle_data['player_defending']:
            player_defense = 5
            if battle_data['is_night']:
                player_defense = 3  # دفاع أقل في الليل
            battle_data['player_defending'] = False
        
        # ضرر العدو
        enemy_damage = enemy.damage
        
        # تأثير الوقت على العدو
        if battle_data['is_night']:
            enemy_damage = int(enemy_damage * 1.3)  # أعداء أقوى في الليل
        
        # قدرات خاصة للعدو
        if enemy.special == 'explode':
            if random.random() < 0.3:
                enemy_damage *= 2
                battle_data['log'].append(f"💥 {enemy.name} انفجر!")
        
        elif enemy.special == 'steal':
            if random.random() < 0.2:
                inv = player.get_inv()
                items = [s for s in inv.values() if s]
                if items:
                    stolen = random.choice(items)
                    if stolen['amount'] > 0:
                        stolen['amount'] -= 1
                        if stolen['amount'] == 0:
                            for key, val in inv.items():
                                if val == stolen:
                                    inv[key] = None
                                    break
                        battle_data['log'].append(f"🪲 {enemy.name} سرق {stolen['name']}")
                        player.save_inv(inv)
                        self.session.commit()
        
        elif enemy.special == 'tameable' and random.random() < 0.1:
            battle_data['log'].append(f"🐕 {enemy.name} يحاول اللعب معك!")
            enemy_damage = 0
        
        # تخفيض الضرر بالدفاع
        final_damage = max(0, enemy_damage - player_defense)
        
        # هجوم العدو
        if final_damage > 0:
            # هل يهرب العدو؟
            if random.random() < 0.05 and battle_data['enemy_hp'] < 5:
                battle_data['log'].append(f"🏃 {enemy.name} هرب!")
                return 'escaped', battle_data
            
            player_hp = max(0, player_hp - final_damage)
            battle_data['log'].append(f"💢 {enemy.name} ضربك بـ {final_damage} ضرر")
        else:
            battle_data['log'].append(f"🛡️ تصدت هجوم {enemy.name}!")
        
        battle_data['player_hp'] = player_hp
        
        # تجديد البافات
        if battle_data['player_buffs']['regeneration'] > 0:
            heal = min(2, battle_data['player_buffs']['regeneration'])
            player_hp = min(player.max_health, player_hp + heal)
            battle_data['player_hp'] = player_hp
            battle_data['player_buffs']['regeneration'] -= 1
            battle_data['log'].append(f"💚 تتجدد +{heal} HP")
        
        return 'continue', battle_data
    
    def use_heal(self, player, battle_data):
        """استخدام شفاء"""
        if player.has_item('healing_potion'):
            player.remove_item('healing_potion')
            heal_amount = 8
            if battle_data['is_night']:
                heal_amount = 6  # شفاء أقل في الليل
            battle_data['player_hp'] = min(
                battle_data['player_max_hp'],
                battle_data['player_hp'] + heal_amount
            )
            battle_data['log'].append(f"🧪 استخدمت جرعة شفاء +{heal_amount} HP")
            self.session.commit()
            return True, battle_data
        else:
            battle_data['log'].append("❌ ليس لديك جرعة شفاء!")
            return False, battle_data
    
    def try_escape(self, player, battle_data):
        """محاولة الهروب"""
        chance = 40 + player.speed + (battle_data['round'] * 5)
        if battle_data['is_night']:
            chance = int(chance * 0.7)  # هروب أصعب في الليل
        chance = min(90, chance)
        
        if random.random() * 100 < chance:
            battle_data['log'].append("🏃 هربت بنجاح!")
            return True, battle_data
        else:
            battle_data['log'].append("🚫 فشلت في الهروب!")
            return False, battle_data
    
    def check_win(self, player, battle_data):
        """التحقق من الفوز"""
        if battle_data['enemy_hp'] <= 0:
            # مكافآت الفوز
            enemy = battle_data['enemy']
            xp_reward = enemy.xp
            if battle_data['is_night']:
                xp_reward = int(xp_reward * 1.5)  # خبرة أكثر في الليل
            player.add_xp(xp_reward)
            
            drops_text = []
            for item, amt, prob in enemy.drops:
                if random.random() < prob:
                    bonus = random.randint(1, 1 + player.luck // 10)
                    if battle_data['is_night']:
                        bonus = int(bonus * 1.5)  # غنائم أكثر في الليل
                    total_amt = amt + bonus
                    player.add_item(item, total_amt)
                    drops_text.append(f"{item} x{total_amt}")
            
            # ترويض الحيوانات
            if enemy.special == 'tameable' and random.random() < 0.15:
                player.pet = 'wolf'
                drops_text.append("🐺 تم ترويض الذئب!")
            
            battle_data['log'].append(f"🎉 انتصرت على {enemy.name}!")
            battle_data['log'].append(f"⭐ +{xp_reward} XP")
            
            if drops_text:
                battle_data['log'].append(f"📦 {', '.join(drops_text)}")
            
            self.session.commit()
            return 'win', battle_data
        
        if battle_data['player_hp'] <= 0:
            battle_data['log'].append("💀 لقد مت!")
            return 'dead', battle_data
        
        return None, battle_data
    
    def get_random_event(self, player):
        """أحداث عشوائية حسب الوقت"""
        events = []
        
        if player.is_night():
            # أحداث الليل
            if random.random() < 0.2:
                enemy = WorldData.roll_enemy(WorldData.get_area(player.current_area), True)
                if enemy:
                    events.append({
                        'type': 'enemy',
                        'msg': f"⚠️ {enemy.emoji} {enemy.name} يهاجمك!",
                        'enemy': enemy
                    })
            if random.random() < 0.1:
                events.append({
                    'type': 'loot',
                    'msg': "🌙 وجدت صندوقاً في الظلام!",
                    'loot': random.choice(['iron_ore', 'gold_ore', 'diamond'])
                })
        else:
            # أحداث النهار
            if random.random() < 0.15:
                events.append({
                    'type': 'loot',
                    'msg': "🎁 وجدت هدية على الأرض!",
                    'loot': random.choice(['apple', 'bread', 'coal', 'leather'])
                })
            if random.random() < 0.05:
                events.append({
                    'type': 'special',
                    'msg': "🌈 قوس قزح! خبرة مضاعفة!",
                    'xp_bonus': 2
                })
        
        return events
