import os, random, telebot, threading, time
from telebot import types
from database import Session, get_player
from game_mechanics import GameMechanics
from crafting_system import CraftingSystem
from world_data import WorldData

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
session = Session()
gm = GameMechanics(session)

# تخزين مؤقت للجلسات
chop_sessions = {}  # {user_id: {"tree": tree, "blocks_left": n}}
mine_sessions = {}
battle_sessions = {}

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🌳 الغابة", "🕳️ الكهف")
    kb.add("🏘️ القرية", "🏛️ المعبد")
    kb.add("🎒 مخزوني", "🛠️ التصنيع")
    kb.add("🍖 أكل", "🗑️ حذف من المخزون")
    kb.add("❤️ حالتي", "📊 مهاراتي")
    return kb

@bot.message_handler(commands=['start'])
def start(msg):
    p, new = get_player(session, msg.from_user.id, msg.from_user.first_name)
    if new:
        txt = "🌟 *أهلاً بك في عالم ماينكرافت!*\n\nاستخدم الأزرار للتنقل."
    else:
        tod = p.get_time_of_day()
        txt = f"👋 *{p.username}*\n⭐ Lv.{p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}"
    bot.send_message(msg.chat.id, txt, parse_mode='Markdown', reply_markup=menu())

# ===== المناطق =====
@bot.message_handler(func=lambda m: m.text in ["🌳 الغابة", "🕳️ الكهف"])
def area_menu(msg):
    area_name = "forest" if msg.text == "🌳 الغابة" else "cave"
    area = WorldData.get_area(area_name)
    p, _ = get_player(session, msg.from_user.id)
    
    if p.level < area.level_req:
        return bot.reply_to(msg, f"❌ تحتاج مستوى {area.level_req}")
    
    tod = p.get_time_of_day()
    is_night = p.is_night()
    
    txt = f"{area.emoji} *{area.name}* | 🕐 {tod}\n\n"
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    
    # أشجار أو صخور
    if area.trees:
        tree = WorldData.roll_tree(area)
        txt += f"🌳 *{tree.name}* ({tree.total_blocks} مكعبات)\n"
        kb.add(types.InlineKeyboardButton(f"🪓 كسر {tree.name}", callback_data=f"chop_{area_name}"))
    
    if area.rocks:
        rock = WorldData.roll_rock(area)
        txt += f"🪨 *{rock.name}* ({rock.total_blocks} مكعبات)\n"
        kb.add(types.InlineKeyboardButton(f"⛏️ كسر {rock.name}", callback_data=f"mine_{area_name}"))
    
    # حيوانات
    if area.animals:
        animal = WorldData.roll_animal(area)
        if animal:
            txt += f"\n{animal.emoji} *{animal.name}*\n"
            kb.add(types.InlineKeyboardButton(f"🏹 صيد {animal.name}", callback_data=f"hunt_{animal.name}"))
    
    # استكشاف عام
    kb.add(types.InlineKeyboardButton("🔍 استكشاف سريع", callback_data=f"explore_{area_name}"))
    
    if is_night:
        txt += "\n⚠️ *إنه الليل! الأعداء في كل مكان!*"
    
    bot.send_message(msg.chat.id, txt, parse_mode='Markdown', reply_markup=kb)

# ===== تكسير الشجرة =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("chop_"))
def start_chopping(call):
    area_name = call.data.split("_")[1]
    area = WorldData.get_area(area_name)
    p, _ = get_player(session, call.from_user.id)
    
    tree = WorldData.roll_tree(area)
    result = gm.start_chopping(p, tree)
    
    chop_sessions[call.from_user.id] = {"tree": tree, "blocks_left": tree.total_blocks}
    
    txt = f"🪓 *{tree.name}*\nالمكعبات: {tree.total_blocks}\n\n{result['animation']}"
    txt += f"\n\nاضغط الزر لتكسر مكعب!"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
    
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_chop")
def do_chop(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.from_user.id not in chop_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    
    session_data = chop_sessions[call.from_user.id]
    tree = session_data["tree"]
    blocks_left = session_data["blocks_left"]
    
    result = gm.chop_block(p, tree, blocks_left)
    
    if result.get("dead"):
        bot.edit_message_text("💀 لقد مت! ابدأ من جديد /start", call.message.chat.id, call.message.message_id)
        del chop_sessions[call.from_user.id]
        return
    
    if result["done"]:
        txt = f"🌳 *انكسرت الشجرة!*\n\n{result['animation']}\n\n🎁 {', '.join(result['rewards'])}"
        del chop_sessions[call.from_user.id]
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"back_forest"))
    else:
        chop_sessions[call.from_user.id]["blocks_left"] = result["blocks_left"]
        txt = f"🪓 *{tree.name}*\nمتبقي: {result['blocks_left']}/{tree.total_blocks}\n\n{result['animation']}"
        txt += f"\n🎁 {', '.join(result['rewards'])}"
        txt += f"\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🪓 اكسر!", callback_data="do_chop"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
    
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)

# ===== تكسير الحجر =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("mine_"))
def start_mining(call):
    area_name = call.data.split("_")[1]
    area = WorldData.get_area(area_name)
    p, _ = get_player(session, call.from_user.id)
    
    rock = WorldData.roll_rock(area)
    result = gm.start_mining(p, rock)
    
    mine_sessions[call.from_user.id] = {"rock": rock, "blocks_left": rock.total_blocks}
    
    txt = f"⛏️ *{rock.name}*\nالمكعبات: {rock.total_blocks}\n\n{result['animation']}"
    txt += f"\n\nاضغط الزر لتكسر مكعب!"
    
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
    kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
    
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "do_mine")
def do_mine(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.from_user.id not in mine_sessions:
        return bot.answer_callback_query(call.id, "انتهت الجلسة")
    
    session_data = mine_sessions[call.from_user.id]
    rock = session_data["rock"]
    blocks_left = session_data["blocks_left"]
    
    result = gm.mine_block(p, rock, blocks_left)
    
    if result.get("dead"):
        bot.edit_message_text("💀 لقد مت! ابدأ من جديد /start", call.message.chat.id, call.message.message_id)
        del mine_sessions[call.from_user.id]
        return
    
    if result["done"]:
        txt = f"⛏️ *انكسر الحجر!*\n\n{result['animation']}\n\n🎁 {', '.join(result['rewards'])}"
        del mine_sessions[call.from_user.id]
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 رجوع", callback_data=f"back_cave"))
    else:
        mine_sessions[call.from_user.id]["blocks_left"] = result["blocks_left"]
        txt = f"⛏️ *{rock.name}*\nمتبقي: {result['blocks_left']}/{rock.total_blocks}\n\n{result['animation']}"
        txt += f"\n🎁 {', '.join(result['rewards'])}"
        txt += f"\n🍖 {result['hunger']:.1f}/20 | ❤️ {result['health']}/20"
        
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("⛏️ اكسر!", callback_data="do_mine"))
        kb.add(types.InlineKeyboardButton("❌ توقف", callback_data="stop_action"))
    
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)

# ===== صيد الحيوانات =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("hunt_"))
def hunt_animal(call):
    animal_name = call.data[5:]
    p, _ = get_player(session, call.from_user.id)
    
    result = gm.hunt_animal(p, animal_name)
    if "error" in result:
        return bot.answer_callback_query(call.id, result["error"])
    
    txt = f"🏹 صيد {result['animal']}\n\n🎁 {', '.join(result['rewards'])}"
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

# ===== استكشاف سريع =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("explore_"))
def quick_explore(call):
    area_name = call.data.split("_")[1]
    p, _ = get_player(session, call.from_user.id)
    
    is_night = p.is_night()
    enemy = WorldData.roll_enemy(WorldData.get_area(area_name), is_night)
    
    if enemy:
        # بدء قتال
        result = gm.start_battle(p, enemy)
        battle_sessions[call.from_user.id] = {
            "enemy": enemy,
            "enemy_hp": result["enemy_hp"],
            "player_hp": result["player_hp"],
            "log": result["log"],
            "round": 0
        }
        
        txt = f"⚔️ *هجوم!*\n{enemy.emoji} {enemy.name} ظهر فجأة!\n\n❤️ حياتك: {result['player_hp']}\n❤️ العدو: {result['enemy_hp']}"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🗡️ هجوم", callback_data="bat_attack"),
            types.InlineKeyboardButton("🛡️ دفاع", callback_data="bat_defend")
        )
        kb.add(
            types.InlineKeyboardButton("🍖 أكل", callback_data="bat_eat"),
            types.InlineKeyboardButton("🏃 هروب", callback_data="bat_run")
        )
        
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)
    else:
        # مكافأة صغيرة
        rewards = ["apple", "bread", "coal"]
        r = random.choice(rewards)
        p.add_item(r, random.randint(1, 3))
        p.add_xp(3)
        session.commit()
        
        txt = f"🔍 استكشاف سريع...\n\n🎁 وجدت {r}!"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

# ===== القتال =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("bat_"))
def battle_action(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.from_user.id not in battle_sessions:
        return bot.answer_callback_query(call.id, "انتهى القتال")
    
    data = battle_sessions[call.from_user.id]
    action = call.data[4:]
    
    result = gm.battle_action(p, data["enemy"], data["enemy_hp"], data["player_hp"], action, data["log"], data["round"])
    
    if result.get("win"):
        txt = f"🎉 *انتصرت!*\n\n{chr(10).join(result['log'])}"
        if result.get('drops'):
            txt += f"\n\n📦 {', '.join(result['drops'])}"
        txt += f"\n⭐ +{result['xp']}XP"
        del battle_sessions[call.from_user.id]
        kb = None
    elif result.get("escaped"):
        txt = f"🏃 هربت!\n\n{chr(10).join(result['log'])}"
        del battle_sessions[call.from_user.id]
        kb = None
    elif result.get("dead"):
        txt = "💀 لقد مت!\n\nاستخدم /start للعودة"
        del battle_sessions[call.from_user.id]
        kb = None
    else:
        battle_sessions[call.from_user.id].update({
            "enemy_hp": result["enemy_hp"],
            "player_hp": result["player_hp"],
            "log": result["log"],
            "round": result["round"]
        })
        
        txt = f"⚔️ *الجولة {result['round']}*\n\n{chr(10).join(result['log'][-3:])}"
        txt += f"\n\n❤️ حياتك: {result['player_hp']}\n❤️ {data['enemy'].name}: {result['enemy_hp']}/{data['enemy'].health}"
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("🗡️ هجوم", callback_data="bat_attack"),
            types.InlineKeyboardButton("🛡️ دفاع", callback_data="bat_defend")
        )
        kb.add(
            types.InlineKeyboardButton("🍖 أكل", callback_data="bat_eat"),
            types.InlineKeyboardButton("🏃 هروب", callback_data="bat_run")
        )
    
    bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)

# ===== توقف =====
@bot.callback_query_handler(func=lambda c: c.data == "stop_action")
def stop_action(call):
    uid = call.from_user.id
    chop_sessions.pop(uid, None)
    mine_sessions.pop(uid, None)
    battle_sessions.pop(uid, None)
    bot.edit_message_text("👋 تم التوقف", call.message.chat.id, call.message.message_id)

# ===== رجوع =====
@bot.callback_query_handler(func=lambda c: c.data.startswith("back_"))
def go_back(call):
    area_name = call.data.split("_")[1]
    area_menu(call.message)
    # بنفس الاسم عشان تنعاد
    class FakeMsg:
        def __init__(self, msg):
            self.text = "🌳 الغابة" if area_name == "forest" else "🕳️ الكهف"
            self.from_user = msg.from_user
            self.chat = msg.chat
    area_menu(FakeMsg(call.message))

# ===== القرية =====
@bot.message_handler(func=lambda m: m.text == "🏘️ القرية")
def village(msg):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("😴 نوم", callback_data="v_sleep"),
        types.InlineKeyboardButton("📋 مهمة", callback_data="v_quest"),
        types.InlineKeyboardButton("🛒 متجر", callback_data="v_shop")
    )
    bot.send_message(msg.chat.id, "🏘️ *القرية*", parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data in ["v_sleep", "v_quest", "v_shop"])
def village_actions(call):
    p, _ = get_player(session, call.from_user.id)
    
    if call.data == "v_sleep":
        res = gm.sleep(p)
        if "error" in res:
            bot.answer_callback_query(call.id, res["error"])
        else:
            bot.edit_message_text(f"😴 {res['msg']}\n❤️ {res['hp']} | 🍖 {res['hunger']}", call.message.chat.id, call.message.message_id)
    
    elif call.data == "v_quest":
        quests = [
            ("الفلاح العطشان", "milk", 1, "bread", 3),
            ("الحداد", "iron_ore", 3, "iron_sword", 1),
        ]
        q = random.choice(quests)
        if p.has_item(q[1], q[2]):
            p.remove_item(q[1], q[2])
            p.add_item(q[3], q[4])
            session.commit()
            bot.answer_callback_query(call.id, f"✅ {q[0]}! +{q[3]}")
        else:
            bot.answer_callback_query(call.id, f"❌ تحتاج {q[2]} {q[1]}")
    
    elif call.data == "v_shop":
        txt = "🛒 *متجر*\n/buy تفاح = 2 خشب\n/buy لحم = 1 حديد"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

# ===== مخزوني =====
@bot.message_handler(func=lambda m: m.text == "🎒 مخزوني")
def inventory(msg):
    p, _ = get_player(session, msg.from_user.id)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.reply_to(msg, "📭 المخزون فارغ")
    
    txt = "🎒 *مخزونك:*\n\n"
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    
    equip = p.get_equip()
    txt += f"\n🎽 *المعدات:* {equip.get('weapon','لا شيء')}"
    
    bot.send_message(msg.chat.id, txt, parse_mode='Markdown')

# ===== حذف من المخزون =====
@bot.message_handler(func=lambda m: m.text == "🗑️ حذف من المخزون")
def delete_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.reply_to(msg, "📭 المخزون فارغ")
    
    txt = "🗑️ *اختر عنصر للحذف:*\n\n"
    kb = types.InlineKeyboardMarkup(row_width=3)
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
        kb.add(types.InlineKeyboardButton(f"🗑️ {idx+1}", callback_data=f"del_{idx}"))
    
    bot.send_message(msg.chat.id, txt, parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_item(call):
    p, _ = get_player(session, call.from_user.id)
    slot_num = int(call.data.split("_")[1])
    p.delete_slot(slot_num)
    session.commit()
    bot.edit_message_text(f"✅ تم حذف العنصر من الخانة {slot_num+1}", call.message.chat.id, call.message.message_id)

# ===== تصنيع =====
@bot.message_handler(func=lambda m: m.text == "🛠️ التصنيع")
def craft_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    recipes = CraftingSystem.get_recipes(p)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(recipes[:20]):
        kb.add(types.InlineKeyboardButton(f"{r['emoji']} {r['name']}", callback_data=f"craft_{i}"))
    bot.send_message(msg.chat.id, "🛠️ *التصنيع*", parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("craft_"))
def do_craft(call):
    p, _ = get_player(session, call.from_user.id)
    idx = int(call.data.split("_")[1])
    recipes = CraftingSystem.get_recipes(p)
    if idx < len(recipes):
        ok, msg = CraftingSystem.craft(p, recipes[idx])
        session.commit()
        bot.answer_callback_query(call.id, msg)

# ===== أكل =====
@bot.message_handler(func=lambda m: m.text == "🍖 أكل")
def eat_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    inv = p.get_inv()
    food_list = ["apple","bread","cooked_beef","tropical_fruit","honey","golden_apple","milk","egg","raw_beef","raw_chicken"]
    foods = {s["name"]: s["amount"] for s in inv.values() if s and s["name"] in food_list}
    
    if not foods:
        return bot.reply_to(msg, "🍖 لا طعام")
    
    kb = types.InlineKeyboardMarkup(row_width=2)
    for f, amt in foods.items():
        kb.add(types.InlineKeyboardButton(f"{f} x{amt}", callback_data=f"eat_{f}"))
    bot.send_message(msg.chat.id, "🍖 *اختر*", parse_mode='Markdown', reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("eat_"))
def do_eat(call):
    p, _ = get_player(session, call.from_user.id)
    food = call.data[4:]
    res = gm.eat(p, food)
    if "error" in res:
        bot.answer_callback_query(call.id, res["error"])
    else:
        txt = f"🍖 {food} | +{res['hunger']} شبع | {res['current']}/20"
        if res.get('effects'):
            txt += "\n" + "\n".join(res['effects'])
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)

# ===== حالتي =====
@bot.message_handler(func=lambda m: m.text == "❤️ حالتي")
def status(msg):
    p, _ = get_player(session, msg.from_user.id)
    titles = p.titles if isinstance(p.titles, list) else []
    tod = p.get_time_of_day()
    txt = f"👤 {p.username} | ⭐ Lv.{p.level}\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🕐 {tod}\n🏅 {', '.join(titles) if titles else 'لا ألقاب'}\n🐺 حيوان: {p.pet or 'لا يوجد'}"
    bot.send_message(msg.chat.id, txt)

# ===== مهاراتي =====
@bot.message_handler(func=lambda m: m.text == "📊 مهاراتي")
def skills(msg):
    p, _ = get_player(session, msg.from_user.id)
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

# ===== شراء =====
@bot.message_handler(commands=['buy'])
def buy(msg):
    p, _ = get_player(session, msg.from_user.id)
    args = msg.text.split()
    if len(args) < 2:
        return bot.reply_to(msg, "/buy تفاح او /buy لحم")
    shop = {"تفاح":{"price":"oak_wood","amt":2,"give":"apple","gamt":3},
            "لحم":{"price":"iron_ore","amt":1,"give":"cooked_beef","gamt":1}}
    item = args[1]
    if item not in shop:
        return bot.reply_to(msg, "❌ غير متوفر")
    s = shop[item]
    if p.has_item(s["price"], s["amt"]):
        p.remove_item(s["price"], s["amt"])
        p.add_item(s["give"], s["gamt"])
        session.commit()
        bot.reply_to(msg, f"✅ اشتريت {item}!")
    else:
        bot.reply_to(msg, f"❌ تحتاج {s['amt']} {s['price']}")

print("🤖 البوت يعمل...")
bot.infinity_polling()
