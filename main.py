import os, random, telebot
from telebot import types
from database import Session, get_player
from game_mechanics import GameMechanics, BattleSystem
from crafting_system import CraftingSystem
from world_data import WorldData
from datetime import datetime

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
session = Session()
gm = GameMechanics(session)
battle_system = BattleSystem(session)

chop_sessions = {}
mine_sessions = {}
battle_sessions = {}

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🌳 الغابة", "🕳️ الكهف")
    kb.add("🏘️ القرية", "🏛️ المعبد")
    kb.add("🎒 مخزوني", "🛠️ التصنيع")
    kb.add("🍖 أكل", "🗑️ حذف")
    kb.add("❤️ حالتي", "📊 مهاراتي")
    return kb

def edit_msg(bot, chat_id, msg_id, text, reply_markup=None):
    """تعديل رسالة بأمان"""
    try:
        if reply_markup:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=reply_markup)
        else:
            bot.edit_message_text(text, chat_id, msg_id)
        return True
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" in str(e):
            return True
        if "message to edit not found" in str(e):
            bot.send_message(chat_id, text, reply_markup=reply_markup)
            return True
        print(f"Edit error: {e}")
        return False

def update_time_and_check_events(player):
    """تحديث الوقت والتحقق من أحداث عشوائية"""
    time_of_day = gm.update_game_time(player)
    
    events = battle_system.get_random_event(player)
    
    # معالجة الأحداث
    for event in events:
        if event['type'] == 'enemy':
            # سيبقى العدو للقتال
            pass
        elif event['type'] == 'loot':
            amt = random.randint(1, 2)
            player.add_item(event['loot'], amt)
            session.commit()
    
    return time_of_day, events

# ===== أمر اختبار لإضافة عناصر =====
@bot.message_handler(commands=['additem'])
def add_item_cmd(msg):
    """أمر لإضافة عنصر للمخزون (للاختبار)"""
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    
    if len(args) < 3:
        return bot.send_message(msg.chat.id, "استخدم: /additem اسم_العنصر العدد\nمثال: /additem oak_wood 5")
    
    item_name = args[1]
    try:
        amount = int(args[2])
    except:
        return bot.send_message(msg.chat.id, "❌ العدد يجب أن يكون رقماً")
    
    success = p.add_item(item_name, amount)
    session.commit()
    
    if success:
        bot.send_message(msg.chat.id, f"✅ تم إضافة {amount} من {item_name}!")
    else:
        bot.send_message(msg.chat.id, f"❌ فشل في إضافة {item_name} (المخزون ممتلئ)")

# ===== أمر لعرض المخزون بشكل مفصل =====
@bot.message_handler(commands=['debug_inv'])
def debug_inv(msg):
    p, _ = get_player(session, msg.from_user.id)
    
    # جلب المخزون مباشرة من قاعدة البيانات
    session.refresh(p)
    
    txt = f"🔍 مخزون {p.username}:\n"
    txt += f"inventory type: {type(p.inventory)}\n"
    
    inv = p.get_inv()
    
    # عد العناصر
    items = []
    for i in range(36):
        slot = inv.get(f"slot_{i}")
        if slot:
            items.append((i, slot))
    
    txt += f"عدد العناصر: {len(items)}\n\n"
    
    if items:
        for idx, slot in items[:10]:
            txt += f"خانة {idx+1}: {slot['name']} x{slot['amount']}\n"
    else:
        txt += "📭 المخزون فارغ"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(commands=['start'])
def start(msg):
    p, new = get_player(session, msg.from_user.id, msg.from_user.first_name)
    session.commit()
    
    if new:
        txt = "🌟 أهلاً بك في عالم ماينكرافت!\n\nاستخدم الأزرار للتنقل."
    else:
        tod = p.get_time_of_day()
        txt = f"👋 {p.username}\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, reply_markup=menu())

@bot.message_handler(func=lambda m: m.text in ["🌳 الغابة", "🕳️ الكهف"])
def area_menu(msg):
    area_name = "forest" if msg.text == "🌳 الغابة" else "cave"
    area = WorldData.get_area(area_name)
    p, _ = get_player(session, msg.from_user.id)
    
    # تحديث الوقت
    time_of_day, events = update_time_and_check_events(p)
    session.commit()
    
    if p.level < area.level_req:
        return bot.send_message(msg.chat.id, f"❌ تحتاج مستوى {area.level_req}")
    
    is_night = p.is_night()
    
    txt = f"{area.emoji} {area.name} | 🕐 {time_of_day}\n\n"
    
    # عرض الأحداث
    for event in events:
        if event['type'] == 'enemy':
            txt += f"⚠️ {event['msg']}\n"
        elif event['type'] == 'loot':
            txt += f"✅ {event['msg']}\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    if area.trees and not is_night:
        tree = WorldData.roll_tree(area)
        txt += f"🌳 {tree.name} ({tree.total_blocks} مكعبات)\n"
        kb.add(types.InlineKeyboardButton(f"🪓 كسر {tree.name}", callback_data=f"chop_{area_name}"))
    
    if area.rocks:
        rock = WorldData.roll_rock(area)
        txt += f"🪨 {rock.name} ({rock.total_blocks} مكعبات)\n"
        kb.add(types.InlineKeyboardButton(f"⛏️ كسر {rock.name}", callback_data=f"mine_{area_name}"))
    
    if area.animals and not is_night:
        animal = WorldData.roll_animal(area)
        if animal:
            txt += f"\n{animal.emoji} {animal.name}\n"
            kb.add(types.InlineKeyboardButton(f"🏹 صيد {animal.name}", callback_data=f"hunt_{animal.name}"))
    
    kb.add(types.InlineKeyboardButton("🔍 استكشاف سريع", callback_data=f"explore_{area_name}"))
    
    if is_night:
        txt += "\n⚠️ 🌙 الليل! الأعداء في كل مكان!"
        txt += "\n💀 أعداء أقوى × غنائم أكثر!"
    
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

# ===== تكسير الشجرة =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("chop_"))
def start_chopping(call):
    area_name = call.data.split("_")[1]
    area = WorldData.get_area(area_name)
    p, _ = get_player(session, call.from_user.id)
    
    # تحديث الوقت
    update_time_and_check_events(p)
    session.commit()
    
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 لا يمكنك قطع الأشجار في الليل!")
    
    tree = WorldData.roll_tree(area)
    result = gm.start_chopping(p, tree)
    session.commit()
    
    chop_sessions[call.from_user.id] = {"tree": tree, "blocks_left": tree.total_blocks}
    
    txt = f"🪓 {tree.name}\nالمكعبات: {tree.total_blocks}\n\n{result['animation']}"
    txt += f"\n\nاضغط الزر لتكسر مكعب!"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_chop")
def do_chop(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.from_user.id not in chop_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    
    data = chop_sessions[call.from_user.id]
    tree = data["tree"]
    blocks_left = data["blocks_left"]
    
    result = gm.chop_block(p, tree, blocks_left)
    session.commit()  # 🔥 مهم جداً!
    
    if result.get("dead"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت! ابدأ من جديد /start")
        del chop_sessions[call.from_user.id]
        return
    
    if result["done"]:
        txt = f"🌳 انكسرت الشجرة!\n\n{result['animation']}\n\n🎁 {', '.join(result['rewards'])}"
        txt += f"\n⭐ +{result['xp']}XP"
        del chop_sessions[call.from_user.id]
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 رجوع للغابة", callback_data="back_forest"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    else:
        chop_sessions[call.from_user.id]["blocks_left"] = result["blocks_left"]
        txt = f"🪓 {tree.name}\nمتبقي: {result['blocks_left']}/{tree.total_blocks}\n\n{result['animation']}"
        txt += f"\n🎁 {', '.join(result['rewards'])}"
        txt += f"\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20"
        txt += f"\n⭐ +{result['xp']}XP"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

# ===== تكسير الحجر =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("mine_"))
def start_mining(call):
    area_name = call.data.split("_")[1]
    area = WorldData.get_area(area_name)
    p, _ = get_player(session, call.from_user.id)
    
    # تحديث الوقت
    update_time_and_check_events(p)
    session.commit()
    
    rock = WorldData.roll_rock(area)
    result = gm.start_mining(p, rock)
    session.commit()
    
    mine_sessions[call.from_user.id] = {"rock": rock, "blocks_left": rock.total_blocks}
    
    txt = f"⛏️ {rock.name}\nالمكعبات: {rock.total_blocks}\n\n{result['animation']}"
    txt += f"\n\nاضغط الزر لتكسر مكعب!"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_mine")
def do_mine(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.from_user.id not in mine_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    
    data = mine_sessions[call.from_user.id]
    rock = data["rock"]
    blocks_left = data["blocks_left"]
    
    result = gm.mine_block(p, rock, blocks_left)
    session.commit()  # 🔥 مهم جداً!
    
    if result.get("dead"):
        edit_msg(bot, call.message.chat.id, call.message.message_id, "💀 لقد مت! ابدأ من جديد /start")
        del mine_sessions[call.from_user.id]
        return
    
    if result["done"]:
        txt = f"⛏️ انكسر الحجر!\n\n{result['animation']}\n\n🎁 {', '.join(result['rewards'])}"
        txt += f"\n⭐ +{result['xp']}XP"
        del mine_sessions[call.from_user.id]
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 رجوع للكهف", callback_data="back_cave"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    else:
        mine_sessions[call.from_user.id]["blocks_left"] = result["blocks_left"]
        txt = f"⛏️ {rock.name}\nمتبقي: {result['blocks_left']}/{rock.total_blocks}\n\n{result['animation']}"
        txt += f"\n🎁 {', '.join(result['rewards'])}"
        txt += f"\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20"
        txt += f"\n⭐ +{result['xp']}XP"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

# ===== صيد الحيوانات =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("hunt_"))
def hunt_animal(call):
    animal_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    # تحديث الوقت
    update_time_and_check_events(p)
    session.commit()
    
    if p.is_night():
        return bot.answer_callback_query(call.id, "🌙 الحيوانات نائمة في الليل!")
    
    result = gm.hunt_animal(p, animal_name)
    session.commit()
    
    if "error" in result:
        return bot.answer_callback_query(call.id, result["error"])
    
    txt = f"🏹 صيد {result['animal']}\n🕐 {p.get_time_of_day()}\n\n🎁 {', '.join(result['rewards'])}"
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

# ===== استكشاف سريع =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_"))
def quick_explore(call):
    area_name = call.data.split("_")[1]
    p, _ = get_player(session, call.from_user.id)
    
    # تحديث الوقت
    time_of_day, events = update_time_and_check_events(p)
    is_night = p.is_night()
    session.commit()
    
    # تحقق من الأحداث أولاً
    for event in events:
        if event['type'] == 'enemy':
            # بدء معركة مع العدو
            enemy = event['enemy']
            battle_data = battle_system.start_battle(p, enemy)
            battle_sessions[call.from_user.id] = battle_data
            
            txt = f"⚔️ هجوم!\n{enemy.emoji} {enemy.name} ظهر فجأة!\n🕐 {time_of_day}\n\n"
            txt += f"❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n"
            txt += f"❤️ {enemy.name}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
            
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"),
                types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend")
            )
            kb.add(
                types.InlineKeyboardButton("🧪 شفاء", callback_data="battle_heal"),
                types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run")
            )
            
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
            return
    
    # استكشاف عادي
    enemy = WorldData.roll_enemy(WorldData.get_area(area_name), is_night)
    
    if enemy:
        battle_data = battle_system.start_battle(p, enemy)
        battle_sessions[call.from_user.id] = battle_data
        
        txt = f"⚔️ هجوم!\n{enemy.emoji} {enemy.name} ظهر فجأة!\n🕐 {time_of_day}\n\n"
        txt += f"❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n"
        txt += f"❤️ {enemy.name}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"),
            types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend")
        )
        kb.add(
            types.InlineKeyboardButton("🧪 شفاء", callback_data="battle_heal"),
            types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run")
        )
        
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)
    else:
        # استكشاف سريع - موارد
        possible_loot = ["apple", "bread", "coal", "iron_ore", "gold_ore", "diamond"]
        if is_night:
            possible_loot = ["coal", "iron_ore", "gold_ore", "diamond"]
        r = random.choice(possible_loot)
        amt = random.randint(1, 2 + p.luck // 10)
        if is_night:
            amt += 1
        p.add_item(r, amt)
        
        xp_reward = 2
        if is_night:
            xp_reward = 4
        p.add_xp(xp_reward)
        session.commit()
        
        txt = f"🔍 استكشاف سريع...\n🕐 {time_of_day}\n\n🎁 وجدت {r} x{amt}!\n⭐ +{xp_reward}XP"
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

# ===== القتال =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("battle_"))
def battle_action(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.from_user.id not in battle_sessions:
        return bot.answer_callback_query(call.id, "انتهى القتال")
    
    battle_data = battle_sessions[call.from_user.id]
    action = call.data[7:]  # battle_attack -> attack
    
    # تحديث الوقت
    time_of_day = gm.update_game_time(p)
    battle_data['is_night'] = p.is_night()
    session.commit()
    
    # تنفيذ الإجراء
    if action == 'attack':
        battle_data = battle_system.player_attack(p, battle_data)
    elif action == 'defend':
        battle_data = battle_system.player_defend(p, battle_data)
    elif action == 'heal':
        success, battle_data = battle_system.use_heal(p, battle_data)
        if not success:
            bot.answer_callback_query(call.id, "❌ ليس لديك جرعة شفاء!")
    elif action == 'run':
        success, battle_data = battle_system.try_escape(p, battle_data)
        if success:
            del battle_sessions[call.from_user.id]
            session.commit()
            txt = f"🏃 هربت بنجاح!\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-5:])
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
            return
        else:
            bot.answer_callback_query(call.id, "🚫 فشلت في الهروب!")
    
    # دور العدو (إذا لم ينته القتال)
    if battle_data['enemy_hp'] > 0 and battle_data['player_hp'] > 0:
        result, battle_data = battle_system.enemy_turn(p, battle_data)
        if result == 'escaped':
            del battle_sessions[call.from_user.id]
            session.commit()
            txt = f"🏃 هرب العدو!\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-5:])
            edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
            return
    
    # التحقق من الفوز أو الموت
    status, battle_data = battle_system.check_win(p, battle_data)
    session.commit()
    
    if status == 'win':
        del battle_sessions[call.from_user.id]
        txt = f"🎉 انتصرت!\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-8:])
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
        return
    
    elif status == 'dead':
        del battle_sessions[call.from_user.id]
        txt = f"💀 لقد مت!\n🕐 {time_of_day}\n\n" + "\n".join(battle_data['log'][-5:])
        txt += "\n\nاستخدم /start للعودة"
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)
        return
    
    # تحديث الجلسة
    battle_data['round'] += 1
    battle_sessions[call.from_user.id] = battle_data
    
    # عرض المعركة
    txt = f"⚔️ الجولة {battle_data['round']}\n🕐 {time_of_day}\n\n"
    txt += "\n".join(battle_data['log'][-5:])
    txt += f"\n\n❤️ حياتك: {battle_data['player_hp']}/{battle_data['player_max_hp']}\n"
    txt += f"❤️ {battle_data['enemy'].name}: {battle_data['enemy_hp']}/{battle_data['enemy_max_hp']}"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🗡️ هجوم", callback_data="battle_attack"),
        types.InlineKeyboardButton("🛡️ دفاع", callback_data="battle_defend")
    )
    kb.add(
        types.InlineKeyboardButton("🧪 شفاء", callback_data="battle_heal"),
        types.InlineKeyboardButton("🏃 هروب", callback_data="battle_run")
    )
    
    edit_msg(bot, call.message.chat.id, call.message.message_id, txt, kb)

# ===== توقف =====
@bot.callback_query_handler(func=lambda c: c.data == "stop_action")
def stop_action(call):
    uid = call.from_user.id
    chop_sessions.pop(uid, None)
    mine_sessions.pop(uid, None)
    battle_sessions.pop(uid, None)
    edit_msg(bot, call.message.chat.id, call.message.message_id, "👋 تم التوقف")

# ===== رجوع =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("back_"))
def go_back(call):
    area = call.data.split("_")[1]
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"👋 ارجع للأزرار الرئيسية واختار المنطقة")

# ===== القرية =====
@bot.message_handler(func=lambda m: m.text == "🏘️ القرية")
def village(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_check_events(p)
    session.commit()
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("😴 نوم", callback_data="v_sleep"),
        types.InlineKeyboardButton("📋 مهمة", callback_data="v_quest"),
        types.InlineKeyboardButton("🛒 متجر", callback_data="v_shop")
    )
    bot.send_message(msg.chat.id, f"🏘️ القرية\n🕐 {p.get_time_of_day()}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ["v_sleep", "v_quest", "v_shop"])
def village_actions(call):
    p, _ = get_player(session, call.from_user.id)
    update_time_and_check_events(p)
    
    if call.data == "v_sleep":
        res = gm.sleep(p)
        session.commit()
        if "error" in res:
            bot.answer_callback_query(call.id, res["error"])
        else:
            edit_msg(bot, call.message.chat.id, call.message.message_id, f"😴 {res['msg']}\n❤️ {res['hp']} | 🍖 {res['hunger']}\n🌅 استيقظت فجراً!")
    
    elif call.data == "v_quest":
        quests = [
            ("الفلاح العطشان", "milk", 1, "bread", 3),
            ("الحداد", "iron_ore", 3, "iron_sword", 1),
        ]
        q = random.choice(quests)
        if p.has_item(q[1], q[2]):
            p.remove_item(q[1], q[2])
            p.add_item(q[3], q[4])
            p.add_xp(5)
            session.commit()
            bot.answer_callback_query(call.id, f"✅ {q[0]}! +{q[3]} +5XP")
        else:
            bot.answer_callback_query(call.id, f"❌ تحتاج {q[2]} {q[1]}")
    
    elif call.data == "v_shop":
        txt = f"🛒 متجر 🛒\n🕐 {p.get_time_of_day()}\n\n/buy تفاح = 2 خشب\n/buy لحم = 1 حديد"
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

# ===== مخزوني (المعدل) =====
@bot.message_handler(func=lambda m: m.text == "🎒 مخزوني")
def inventory(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_check_events(p)
    
    # تحديث الكائن من قاعدة البيانات
    session.refresh(p)
    
    inv = p.get_inv()
    
    # طباعة للتصحيح في الكونسول
    print(f"🔍 مخزون {p.username}: {inv}")
    
    items = []
    for i in range(36):
        slot = inv.get(f"slot_{i}")
        if slot:
            items.append((i, slot))
    
    if not items:
        return bot.send_message(msg.chat.id, f"📭 المخزون فارغ\n\n🕐 {p.get_time_of_day()}")
    
    txt = f"🎒 مخزونك:\n🕐 {p.get_time_of_day()}\n\n"
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    
    equip = p.get_equip()
    txt += f"\n🎽 المعدات: {equip.get('weapon','لا شيء')}"
    
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "🗑️ حذف")
def delete_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.send_message(msg.chat.id, "📭 المخزون فارغ")
    
    txt = "🗑️ اختر عنصر للحذف:\n\n"
    kb = types.InlineKeyboardMarkup(row_width=3)
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
        kb.add(types.InlineKeyboardButton(f"🗑️ {idx+1}", callback_data=f"del_{idx}"))
    
    bot.send_message(msg.chat.id, txt, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_item(call):
    p, _ = get_player(session, call.from_user.id)
    slot_num = int(call.data.split("_")[1])
    p.delete_slot(slot_num)
    session.commit()
    edit_msg(bot, call.message.chat.id, call.message.message_id, f"✅ تم حذف العنصر من الخانة {slot_num+1}")

@bot.message_handler(func=lambda m: m.text == "🛠️ التصنيع")
def craft_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_check_events(p)
    session.commit()
    
    recipes = CraftingSystem.get_recipes(p)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(recipes[:20]):
        kb.add(types.InlineKeyboardButton(f"{r['emoji']} {r['name']}", callback_data=f"craft_{i}"))
    bot.send_message(msg.chat.id, f"🛠️ التصنيع\n🕐 {p.get_time_of_day()}", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("craft_"))
def do_craft(call):
    p, _ = get_player(session, call.from_user.id)
    idx = int(call.data.split("_")[1])
    recipes = CraftingSystem.get_recipes(p)
    if idx < len(recipes):
        ok, msg = CraftingSystem.craft(p, recipes[idx])
        session.commit()
        bot.answer_callback_query(call.id, msg)

@bot.message_handler(func=lambda m: m.text == "🍖 أكل")
def eat_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_check_events(p)
    session.refresh(p)
    
    inv = p.get_inv()
    food_list = ["apple","bread","cooked_beef","tropical_fruit","honey","golden_apple","milk","egg","raw_beef","raw_chicken"]
    foods = {s["name"]: s["amount"] for s in inv.values() if s and s["name"] in food_list}
    
    if not foods:
        return bot.send_message(msg.chat.id, "🍖 لا طعام")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for f, amt in foods.items():
        kb.add(types.InlineKeyboardButton(f"{f} x{amt}", callback_data=f"eat_{f}"))
    bot.send_message(msg.chat.id, "🍖 اختر", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("eat_"))
def do_eat(call):
    p, _ = get_player(session, call.from_user.id)
    food = call.data[4:]
    res = gm.eat(p, food)
    session.commit()
    if "error" in res:
        bot.answer_callback_query(call.id, res["error"])
    else:
        txt = f"🍖 {food} | +{res['hunger']} شبع | {res['current']}/20"
        if res.get('effects'):
            txt += "\n" + "\n".join(res['effects'])
        edit_msg(bot, call.message.chat.id, call.message.message_id, txt)

@bot.message_handler(func=lambda m: m.text == "❤️ حالتي")
def status(msg):
    p, _ = get_player(session, msg.from_user.id)
    update_time_and_check_events(p)
    session.refresh(p)
    
    titles = p.titles if isinstance(p.titles, list) else []
    tod = p.get_time_of_day()
    txt = f"👤 {p.username} | ⭐ Lv.{p.level}\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}\n🏅 {', '.join(titles) if titles else 'لا ألقاب'}\n🐺 حيوان: {p.pet or 'لا يوجد'}"
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📊 مهاراتي")
def skills(msg):
    p, _ = get_player(session, msg.from_user.id)
    session.refresh(p)
    
    txt = f"⚔️ قوة: {p.strength} | 💨 سرعة: {p.speed}\n💪 تحمل: {p.endurance} | 🍀 حظ: {p.luck}\n🎯 نقاط: {p.skill_points}"
    if p.skill_points > 0:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("⚔️", callback_data="sk_strength"),
            types.InlineKeyboardButton("💨", callback_data="sk_speed"),
            types.InlineKeyboardButton("💪", callback_data="sk_endurance"),
            types.InlineKeyboardButton("🍀", callback_data="sk_luck")
        )
        bot.send_message(msg.chat.id, txt, reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, txt)

@bot.callback_query_handler(func=lambda c: c.data.startswith("sk_"))
def upgrade_skill(call):
    p, _ = get_player(session, call.from_user.id)
    sk = call.data[3:]
    if p.skill_points > 0:
        setattr(p, sk, min(100, getattr(p, sk)+1))
        if sk == "endurance":
            p.max_health += 2
            p.current_health += 2
        p.skill_points -= 1
        session.commit()
        bot.answer_callback_query(call.id, f"✅ {sk} +1")
        skills(call.message)

@bot.message_handler(commands=['buy'])
def buy(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 2:
        return bot.send_message(msg.chat.id, "/buy تفاح او /buy لحم")
    shop = {"تفاح":{"price":"oak_wood","amt":2,"give":"apple","gamt":3},
            "لحم":{"price":"iron_ore","amt":1,"give":"cooked_beef","gamt":1}}
    item = args[1]
    if item not in shop:
        return bot.send_message(msg.chat.id, "❌ غير متوفر")
    s = shop[item]
    if p.has_item(s["price"], s["amt"]):
        p.remove_item(s["price"], s["amt"])
        p.add_item(s["give"], s["gamt"])
        session.commit()
        bot.send_message(msg.chat.id, f"✅ اشتريت {item}!")
    else:
        bot.send_message(msg.chat.id, f"❌ تحتاج {s['amt']} {s['price']}")

print("🤖 البوت يعمل...")
bot.infinity_polling()
