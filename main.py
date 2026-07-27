import os
import telebot
from telebot import types
from datetime import datetime
import random
from sqlalchemy import text
from database import Player, WorldEvent, Session, engine, get_or_create_player
from game_mechanics import GameMechanics
from world_data import WorldData

# ====== إصلاح قاعدة البيانات تلقائياً ======
def fix_database():
    try:
        with engine.connect() as conn:
            columns_to_add = [
                ("dragon_crystals", "INTEGER DEFAULT 6"),
                ("dragon_sword_hits", "INTEGER DEFAULT 0"),
                ("final_blows", "INTEGER DEFAULT 0"),
            ]
            
            for col_name, col_type in columns_to_add:
                try:
                    conn.execute(text(
                        f"ALTER TABLE players ADD COLUMN IF NOT EXISTS {col_name} {col_type}"
                    ))
                    conn.commit()
                    print(f"✅ عمود {col_name}")
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"⚠️ {col_name}: {e}")
            
            print("✅ قاعدة البيانات محدثة")
    except Exception as e:
        print(f"❌ خطأ: {e}")

fix_database()

# ====== تهيئة البوت ======
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
bot = telebot.TeleBot(TOKEN)
session = Session()
game = GameMechanics(session)
temple_sessions = {}

def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        "🌳 استكشاف الغابة", "🕳️ استكشاف الكهف",
        "🏘️ الذهاب للقرية", "🏛️ دخول المعبد",
        "🔥 النذر", "🎒 مخزوني",
        "🛠️ التصنيع", "🍖 أكل",
        "❤️ حالتي", "📊 مهاراتي",
        "ℹ️ مساعدة"
    ]
    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        username = message.from_user.username or message.from_user.first_name
        
        player, is_new = get_or_create_player(session, user_id, username)
        
        if is_new:
            welcome_text = """
🌟 *أهلاً بك في عالم ماينكرافت!*

🎮 *ابدأ رحلتك الآن:*
• 🌳 استكشف الغابة للأخشاب والطعام
• 🕳️ ادخل الكهوف للمعادن
• 🏘️ زر القرية للتجارة والمهام
• 🏛️ تحدى المعبد للألغاز
• 🛠️ اصنع أدواتك وأسلحتك

استخدم الأزرار أدناه للتنقل 👇
            """
        else:
            welcome_text = f"""
👋 *مرحباً بعودتك {player.username}!*

📊 *حالتك:*
⭐ المستوى: {player.level} | XP: {player.xp}/{player.level * 10}
❤️ الصحة: {player.current_health}/{player.max_health}
🍖 الجوع: {player.current_hunger}/{player.max_hunger}
🗺️ المنطقة: {player.current_area}
            """
        
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "🌳 استكشاف الغابة")
def explore_forest_cmd(message):
    process_exploration(message, "forest")

@bot.message_handler(func=lambda msg: msg.text == "🕳️ استكشاف الكهف")
def explore_cave_cmd(message):
    process_exploration(message, "cave")

@bot.message_handler(func=lambda msg: msg.text == "🔥 النذر")
def explore_nether_cmd(message):
    process_exploration(message, "cave")

def process_exploration(message, area_name):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        if not player:
            bot.reply_to(message, "❌ حدث خطأ. جرب /start")
            return
        
        wait_msg = bot.reply_to(message, f"🔍 جاري استكشاف {area_name}...")
        
        result = game.explore_area(player, area_name)
        
        if "error" in result:
            bot.edit_message_text(
                f"❌ {result['error']}",
                message.chat.id,
                wait_msg.message_id
            )
            return
        
        response = f"{result['emoji']} *استكشاف {result['area']}*\n\n"
        response += f"⏱️ الوقت: {result['explore_time']} ثانية\n\n"
        
        if result['rewards']:
            response += "🎁 *الموارد:*\n"
            for reward in result['rewards']:
                response += f"• {reward}\n"
        
        if result.get('enemy'):
            enemy_data = result['enemy']
            response += f"\n⚔️ *{enemy_data['enemy_emoji']} {enemy_data['enemy_name']}!*\n"
            
            if enemy_data.get('victory'):
                response += "✅ انتصرت!\n"
                if enemy_data.get('drops'):
                    response += "📦 *الغنائم:*\n"
                    for drop in enemy_data['drops']:
                        response += f"• {drop}\n"
                response += f"⭐ +{enemy_data['xp_reward']} XP\n"
            else:
                response += f"💔 خسرت {enemy_data.get('health_lost', 0)} صحة\n"
        
        if result.get('event'):
            response += f"\n🎲 {result['event']['message']}\n"
        
        response += f"\n⭐ +{result['xp_gained']} XP"
        response += f"\n🍖 الجوع: {result['current_hunger']}/20"
        response += f"\n❤️ الصحة: {result['current_health']}/20"
        
        if result.get('starvation'):
            response += f"\n\n{result['starvation']}"
        
        bot.edit_message_text(
            response,
            message.chat.id,
            wait_msg.message_id,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "🏘️ الذهاب للقرية")
def village_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("😴 النوم", callback_data="village_sleep"),
        types.InlineKeyboardButton("📋 مهمة", callback_data="village_quest"),
        types.InlineKeyboardButton("🛒 المتجر", callback_data="village_shop")
    )
    
    bot.send_message(
        message.chat.id,
        "🏘️ *مرحباً بك في القرية!*",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == "🏛️ دخول المعبد")
def temple_start(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        result = game.explore_temple(player)
        
        if "error" in result:
            bot.reply_to(message, f"❌ {result['error']}")
            return
        
        temple_sessions[user_id] = {
            "current_room": 1,
            "rooms": result['rooms']
        }
        
        response = f"🏛️ *المعبد*\n\n{result['message']}\n\n"
        response += f"*الغرفة 1:* {result['rooms'][0]['name']}\n"
        response += result['rooms'][0]['description']
        
        markup = types.InlineKeyboardMarkup(row_width=3)
        for i in range(1, 4):
            markup.add(types.InlineKeyboardButton(f"🚪 {i}", callback_data=f"temple_1_{i}"))
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "🎒 مخزوني")
def show_inventory(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        inv = player.get_inventory()
        
        response = "🎒 *مخزونك:*\n\n"
        items_found = False
        
        for i in range(36):
            slot_key = f"slot_{i}"
            item = inv.get(slot_key)
            if item and item.get("name"):
                items_found = True
                response += f"{i+1}. {item['name']} x{item['amount']}\n"
        
        if not items_found:
            response += "📭 المخزون فارغ\n"
        
        equip = player.get_equipment()
        response += "\n🎽 *المعدات:*\n"
        for slot, item in equip.items():
            response += f"• {slot}: {item if item else 'فارغ'}\n"
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "🍖 أكل")
def eat_menu(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        inv = player.get_inventory()
        foods = {}
        food_emojis = {
            "apple": "🍎", "bread": "🍞", "cooked_beef": "🥩",
            "tropical_fruit": "🥭", "honey": "🍯", "milk": "🥛", "egg": "🥚"
        }
        
        for slot_data in inv.values():
            if slot_data and slot_data.get("name") in food_emojis:
                name = slot_data["name"]
                foods[name] = slot_data["amount"]
        
        if not foods:
            bot.reply_to(message, "🍖 ليس لديك طعام!")
            return
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        for food, amount in foods.items():
            emoji = food_emojis.get(food, "🍖")
            markup.add(types.InlineKeyboardButton(
                f"{emoji} {food} (x{amount})",
                callback_data=f"eat_{food}"
            ))
        
        bot.send_message(
            message.chat.id,
            f"🍖 *اختر الطعام:*\n\nالجوع: {player.current_hunger}/20",
            parse_mode='Markdown',
            reply_markup=markup
        )
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "❤️ حالتي")
def show_status(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        health_bar = "█" * player.current_health + "░" * (player.max_health - player.current_health)
        hunger_bar = "█" * player.current_hunger + "░" * (player.max_hunger - player.current_hunger)
        
        titles = player.get_titles()
        
        response = f"""
❤️ *حالة اللاعب*

👤 *{player.username}*
⭐ *المستوى:* {player.level} ({player.xp}/{player.level * 10} XP)
🏅 *الألقاب:* {', '.join(titles) if titles else 'لا يوجد'}

❤️ *الصحة:* {health_bar} {player.current_health}/{player.max_health}
🍖 *الجوع:* {hunger_bar} {player.current_hunger}/{player.max_hunger}

🗺️ *المنطقة:* {player.current_area}
⚔️ *الضرر:* {game.calculate_player_damage(player)}
🛡️ *الدفاع:* {game.calculate_player_defense(player)}
        """
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "📊 مهاراتي")
def show_skills(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        response = f"""
📊 *مهاراتك*

🎯 *نقاط المهارة:* {player.skill_points}

⚔️ *القوة:* {player.strength}/100 (+{int(player.strength * 2)}% ضرر)
💨 *السرعة:* {player.speed}/100 (-{int(player.speed * 5)}% وقت)
💪 *التحمّل:* {player.endurance}/100 (+{player.endurance * 2} صحة)
🍀 *الحظ:* {player.luck}/100 (+{int(player.luck * 3)}% موارد)

🔓 *الوصفات:* {len(player.get_recipes())} مستوى
        """
        
        if player.skill_points > 0:
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("⚔️ قوة", callback_data="skill_strength"),
                types.InlineKeyboardButton("💨 سرعة", callback_data="skill_speed"),
                types.InlineKeyboardButton("💪 تحمّل", callback_data="skill_endurance"),
                types.InlineKeyboardButton("🍀 حظ", callback_data="skill_luck")
            )
            response += "\nاختر مهارة لتطويرها:"
            bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(message.chat.id, response, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

@bot.message_handler(func=lambda msg: msg.text == "ℹ️ مساعدة")
def help_cmd(message):
    help_text = """
🎮 *أوامر البوت:*

/start - بدء اللعبة
/buy - الشراء من المتجر

*الأزرار الرئيسية:*
🌳 استكشاف الغابة
🕳️ استكشاف الكهف
🏘️ الذهاب للقرية
🏛️ دخول المعبد
🎒 مخزوني
🛠️ التصنيع
🍖 أكل
❤️ حالتي
📊 مهاراتي

*نصائح:*
• ابدأ بجمع الخشب من الغابة
• اصنع أدوات في التصنيع
• نم في القرية لاستعادة الصحة
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['buy'])
def buy_item(message):
    try:
        user_id = message.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "استخدم: /buy [السلعة]")
            return
        
        item = args[1]
        shop = {
            "تفاح": {"price_item": "oak_wood", "price": 2, "give": "apple", "amount": 3},
            "لحم": {"price_item": "iron_ore", "price": 1, "give": "cooked_beef", "amount": 1},
        }
        
        if item not in shop:
            bot.reply_to(message, "❌ سلعة غير متوفرة")
            return
        
        data = shop[item]
        if not player.has_item(data["price_item"], data["price"]):
            bot.reply_to(message, f"❌ تحتاج {data['price']} {data['price_item']}")
            return
        
        player.remove_item(data["price_item"], data["price"])
        player.add_item(data["give"], data["amount"])
        session.commit()
        bot.reply_to(message, f"✅ تم شراء {item}!")
        
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ: {str(e)}")

# ====== معالجة الأزرار ======
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        user_id = call.from_user.id  # ✅ بدون str()
        player, _ = get_or_create_player(session, user_id)
        
        if not player:
            bot.answer_callback_query(call.id, "❌ حدث خطأ")
            return
        
        data = call.data
        
        if data.startswith("temple_"):
            parts = data.split("_")
            room = int(parts[1])
            answer = parts[2]
            
            result = game.solve_temple_puzzle(player, room, answer)
            
            if result.get("temple_complete"):
                bot.edit_message_text(
                    f"🎉 *المعبد مكتمل!*\n\n{result['message']}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
                if user_id in temple_sessions:
                    del temple_sessions[user_id]
            
            elif result.get("next_room"):
                temple_data = temple_sessions.get(user_id, {})
                next_room = result["next_room"]
                
                if next_room <= 5 and temple_data:
                    room_data = temple_data['rooms'][next_room - 1]
                    response = f"🏛️ *الغرفة {next_room}:* {room_data['name']}\n\n"
                    
                    if next_room == 2:
                        response += f"سؤال: {room_data['question']}"
                        markup = types.InlineKeyboardMarkup()
                        markup.add(
                            types.InlineKeyboardButton("أحمر", callback_data="temple_2_أحمر"),
                            types.InlineKeyboardButton("8", callback_data="temple_2_8"),
                            types.InlineKeyboardButton("ألماس", callback_data="temple_2_ألماس")
                        )
                    elif next_room == 3:
                        response += room_data['description']
                        markup = types.InlineKeyboardMarkup(row_width=3)
                        markup.add(
                            types.InlineKeyboardButton("👈 يسار", callback_data="temple_3_يسار"),
                            types.InlineKeyboardButton("👆 وسط", callback_data="temple_3_وسط"),
                            types.InlineKeyboardButton("👉 يمين", callback_data="temple_3_يمين")
                        )
                    else:
                        response += room_data['description']
                        markup = types.InlineKeyboardMarkup(row_width=3)
                        for i in range(1, 4):
                            markup.add(types.InlineKeyboardButton(
                                f"اختيار {i}",
                                callback_data=f"temple_{next_room}_{i}"
                            ))
                    
                    bot.edit_message_text(
                        response,
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
            else:
                bot.answer_callback_query(call.id, result.get('message', ''))
        
        elif data.startswith("eat_"):
            food = data.replace("eat_", "")
            result = game.eat_food(player, food)
            
            if "error" in result:
                bot.answer_callback_query(call.id, result['error'])
            else:
                response = f"🍖 أكلت {food}!\n"
                response += f"🍖 شبع: +{result['hunger_restored']}\n"
                response += f"المستوى: {result['current_hunger']}/20\n"
                
                if result.get('effects'):
                    response += "\n" + "\n".join(result['effects'])
                
                bot.edit_message_text(
                    response,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
        
        elif data.startswith("skill_"):
            skill = data.replace("skill_", "")
            if player.skill_points > 0:
                if skill == "strength":
                    player.strength = min(100, player.strength + 1)
                elif skill == "speed":
                    player.speed = min(100, player.speed + 1)
                elif skill == "endurance":
                    player.endurance = min(100, player.endurance + 1)
                    player.max_health += 2
                    player.current_health = min(player.max_health, player.current_health + 2)
                elif skill == "luck":
                    player.luck = min(100, player.luck + 1)
                
                player.skill_points -= 1
                session.commit()
                bot.answer_callback_query(call.id, f"✅ تمت ترقية {skill}!")
                show_skills(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ لا تملك نقاط مهارة")
        
        elif data == "village_sleep":
            result = game.sleep_in_village(player)
            if "error" in result:
                bot.answer_callback_query(call.id, result['error'])
            else:
                bot.edit_message_text(
                    f"😴 {result['message']}\n\n❤️ الصحة: {result['health']}/20\n🍖 الجوع: {result['hunger']}/20",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
        
        elif data == "village_quest":
            quests = [
                {"name": "الفلاح العطشان", "desc": "أحضر حليباً", "reward": "خبز x3", "need": "milk"},
                {"name": "الحداد المحتاج", "desc": "أحضر 3 حديد", "reward": "سيف حديدي", "need": "iron_ore"}
            ]
            quest = random.choice(quests)
            
            if quest['need'] and player.has_item(quest['need'], 1 if quest['need'] == 'milk' else 3):
                player.remove_item(quest['need'], 1 if quest['need'] == 'milk' else 3)
                reward_name = quest['reward'].split()[0]
                reward_amount = int(quest['reward'].split('x')[1]) if 'x' in quest['reward'] else 1
                player.add_item(reward_name, reward_amount)
                session.commit()
                bot.edit_message_text(
                    f"✅ *أكملت المهمة!*\n\nالمكافأة: {quest['reward']}",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
            else:
                bot.edit_message_text(
                    f"📋 *المهمة:* {quest['name']}\n{quest['desc']}\n💰 المكافأة: {quest['reward']}\n\n❌ لا تملك المتطلبات!",
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode='Markdown'
                )
        
        elif data == "village_shop":
            shop_text = """
🛒 *متجر القرية*

• 🍎 تفاح: 2 خشب بلوط
• 🥩 لحم مطبوخ: 1 حديد خام

/buy تفاح
/buy لحم
            """
            bot.edit_message_text(
                shop_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ خطأ: {str(e)}")
        print(f"خطأ في callback: {e}")

# ====== تشغيل البوت ======
if __name__ == "__main__":
    print("🤖 بوت ماينكرافت يعمل...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
