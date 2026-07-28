import os, random, telebot
from telebot import types
from database import Session, get_player
from game_mechanics import GameMechanics
from crafting_system import CraftingSystem

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = telebot.TeleBot(TOKEN)
session = Session()
gm = GameMechanics(session)
temples = {}

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🌳 غابة","🕳️ كهف","🏘️ قرية","🏛️ معبد","🔥 نذر","🌌 إندر")
    kb.add("🎒 مخزون","🛠️ تصنيع","🍖 أكل","❤️ حالتي","📊 مهاراتي")
    return kb

def find_food(player):
    inv = player.get_inv()
    foods = {}
    food_list = ["apple","bread","cooked_beef","tropical_fruit","honey","golden_apple","milk","egg","raw_beef","raw_chicken"]
    for s in inv.values():
        if s and s.get("name") in food_list:
            foods[s["name"]] = s["amount"]
    return foods

@bot.message_handler(commands=['start'])
def start(msg):
    p, new = get_player(session, msg.from_user.id, msg.from_user.first_name)
    txt = "🌟 *أهلاً بك في عالم ماينكرافت!*" if new else f"👋 *مرحباً {p.username}!*\n⭐ مستوى {p.level} | ❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20"
    bot.send_message(msg.chat.id, txt, parse_mode='Markdown', reply_markup=menu())

@bot.message_handler(func=lambda m: m.text in ["🌳 غابة","🕳️ كهف","🔥 نذر","🌌 إندر"])
def explore(msg):
    area_map = {"🌳 غابة":"forest","🕳️ كهف":"cave","🔥 نذر":"nether","🌌 إندر":"end"}
    p, _ = get_player(session, msg.from_user.id)
    wait = bot.reply_to(msg, "🔍 استكشاف...")
    res = gm.explore(p, area_map[msg.text])
    if "error" in res:
        bot.edit_message_text(f"❌ {res['error']}", msg.chat.id, wait.message_id)
        return
    
    txt = f"{res['emoji']} *{res['area']}* | ⏱️ {res['time']}s\n\n🎁 *موارد:*\n"
    txt += "\n".join(f"• {r}" for r in res['rewards'])
    if res.get('enemy'):
        e = res['enemy']
        txt += f"\n\n⚔️ *{e['emoji']} {e['name']}* - {'✅ انتصرت' if e.get('win') else '💔 هُزمت'}"
        if e.get('drops'): txt += "\n📦 " + ", ".join(e['drops'])
    if res.get('event'): txt += f"\n\n🎲 {res['event']['msg']}"
    txt += f"\n\n⭐ +{res['xp']}XP | 🍖 {res['hunger']}/20 | ❤️ {res['health']}/20"
    if res.get('starve'): txt += f"\n{res['starve']}"
    bot.edit_message_text(txt, msg.chat.id, wait.message_id, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🏘️ قرية")
def village(msg):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(types.InlineKeyboardButton("😴 نوم", callback_data="v_sleep"),
           types.InlineKeyboardButton("📋 مهمة", callback_data="v_quest"),
           types.InlineKeyboardButton("🛒 متجر", callback_data="v_shop"))
    bot.send_message(msg.chat.id, "🏘️ *القرية*", parse_mode='Markdown', reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🏛️ معبد")
def temple(msg):
    p, _ = get_player(session, msg.from_user.id)
    res = gm.temple(p)
    if "error" in res:
        bot.reply_to(msg, f"❌ {res['error']}")
        return
    temples[msg.from_user.id] = 1
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(*[types.InlineKeyboardButton(str(i), callback_data=f"tm_1_{i}") for i in range(1,4)])
    bot.send_message(msg.chat.id, f"🏛️ *الغرفة 1: الأبواب*\nاختر باب (1-3)", parse_mode='Markdown', reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🎒 مخزون")
def inv(msg):
    p, _ = get_player(session, msg.from_user.id)
    inv = p.get_inv()
    items = [(i, s) for i, s in enumerate(inv.values()) if s]
    if not items:
        return bot.reply_to(msg, "📭 فارغ")
    # Pagination - show first 18
    txt = "🎒 *مخزونك:*\n\n"
    for idx, slot in items[:18]:
        txt += f"{idx+1}. {slot['name']} x{slot['amount']}\n"
    bot.send_message(msg.chat.id, txt, parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🛠️ تصنيع")
def craft_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    recipes = CraftingSystem.get_recipes(p)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(recipes[:20]):
        kb.add(types.InlineKeyboardButton(f"{r['emoji']} {r['name']}", callback_data=f"craft_{i}"))
    bot.send_message(msg.chat.id, "🛠️ *التصنيع*", parse_mode='Markdown', reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "🍖 أكل")
def eat_menu(msg):
    p, _ = get_player(session, msg.from_user.id)
    foods = find_food(p)
    if not foods:
        return bot.reply_to(msg, "🍖 لا طعام")
    kb = types.InlineKeyboardMarkup(row_width=2)
    for f, amt in foods.items():
        kb.add(types.InlineKeyboardButton(f"{f} x{amt}", callback_data=f"eat_{f}"))
    bot.send_message(msg.chat.id, "🍖 *اختر الطعام*", parse_mode='Markdown', reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "❤️ حالتي")
def status(msg):
    p, _ = get_player(session, msg.from_user.id)
    titles = p.titles if isinstance(p.titles, list) else []
    txt = f"👤 {p.username} | ⭐ Lv.{p.level}\n❤️ {p.current_health}/{p.max_health} | 🍖 {p.current_hunger}/20\n🏅 {', '.join(titles) if titles else 'لا ألقاب'}"
    bot.send_message(msg.chat.id, txt)

@bot.message_handler(func=lambda m: m.text == "📊 مهاراتي")
def skills(msg):
    p, _ = get_player(session, msg.from_user.id)
    txt = f"⚔️ قوة: {p.strength} | 💨 سرعة: {p.speed}\n💪 تحمل: {p.endurance} | 🍀 حظ: {p.luck}\n🎯 نقاط: {p.skill_points}"
    if p.skill_points > 0:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("⚔️", callback_data="sk_strength"),
               types.InlineKeyboardButton("💨", callback_data="sk_speed"),
               types.InlineKeyboardButton("💪", callback_data="sk_endurance"),
               types.InlineKeyboardButton("🍀", callback_data="sk_luck"))
        bot.send_message(msg.chat.id, txt, reply_markup=kb)
    else:
        bot.send_message(msg.chat.id, txt)

@bot.callback_query_handler(func=lambda c: True)
def callback(call):
    p, _ = get_player(session, call.from_user.id)
    data = call.data
    
    if data.startswith("tm_"):
        _, room, ans = data.split("_")
        res = gm.solve_temple(p, int(room), ans)
        if res.get("gem"):
            bot.edit_message_text(res['msg'], call.message.chat.id, call.message.message_id)
            return
        if res.get("error"):
            bot.answer_callback_query(call.id, res.get('msg','خطأ'))
            return
        if not res.get("win"):
            bot.answer_callback_query(call.id, res['msg'])
            return
        if res.get("next"):
            nr = res['next']
            rooms = ["الأبواب","الأشباح","اللهب","الفخاخ","الكنز"]
            if nr > 5:
                bot.edit_message_text("🎉 نجوت من كل الغرف!", call.message.chat.id, call.message.message_id)
                return
            kb = types.InlineKeyboardMarkup(row_width=3)
            if nr == 2:
                kb.add(*[types.InlineKeyboardButton(a, callback_data=f"tm_2_{a}") for a in ["7","6","8"]])
            elif nr == 3:
                kb.add(*[types.InlineKeyboardButton(a, callback_data=f"tm_3_{a}") for a in ["يمين","يسار","وسط"]])
            else:
                kb.add(*[types.InlineKeyboardButton(str(i), callback_data=f"tm_{nr}_{i}") for i in range(1,4)])
            bot.edit_message_text(f"🏛️ *الغرفة {nr}: {rooms[nr-1]}*", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=kb)
    
    elif data.startswith("craft_"):
        idx = int(data.split("_")[1])
        recipes = CraftingSystem.get_recipes(p)
        if idx < len(recipes):
            r = recipes[idx]
            ok, msg = CraftingSystem.craft(p, r)
            session.commit()
            bot.answer_callback_query(call.id, msg)
    
    elif data.startswith("eat_"):
        food = data[4:]
        res = gm.eat(p, food)
        if "error" in res:
            bot.answer_callback_query(call.id, res['error'])
        else:
            txt = f"🍖 {food} | +{res['hunger']} شبع | {res['current']}/20"
            if res.get('effects'): txt += "\n" + "\n".join(res['effects'])
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id)
    
    elif data.startswith("sk_"):
        sk = data[3:]
        if p.skill_points > 0:
            setattr(p, sk, min(100, getattr(p, sk)+1))
            if sk == "endurance":
                p.max_health += 2
                p.current_health += 2
            p.skill_points -= 1
            session.commit()
            bot.answer_callback_query(call.id, f"✅ {sk} +1")
            skills(call.message)
    
    elif data == "v_sleep":
        res = gm.sleep(p)
        if "error" in res:
            bot.answer_callback_query(call.id, res['error'])
        else:
            bot.edit_message_text(f"😴 {res['msg']}\n❤️ {res['hp']} | 🍖 {res['hunger']}", call.message.chat.id, call.message.message_id)
    
    elif data == "v_quest":
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
            bot.answer_callback_query(call.id, f"❌ {q[0]}: تحتاج {q[2]} {q[1]}")
    
    elif data == "v_shop":
        txt = "🛒 *متجر*\n/buy تفاح = 2 خشب\n/buy لحم = 1 حديد"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown')

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
