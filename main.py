import os
import telebot
from telebot import types
from datetime import datetime
from database import Player, Session
from game_mechanics import GameMechanics
from crafting_system import CraftingSystem
from world_data import WorldData

# تهيئة البوت
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
bot = telebot.TeleBot(TOKEN)
session = Session()
game = GameMechanics(session)

# ============ لوحات المفاتيح ============
def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        "🌳 استكشاف الغابة", "🕳️ استكشاف الكهف",
        "🏘️ الذهاب للقرية", "🏛️ دخول المعبد",
        "🔥 النذر", "🌌 الإندر",
        "🎒 مخزوني", "🛠️ التصنيع",
        "🍖 أكل", "❤️ حالتي",
        "📊 مهاراتي", "ℹ️ مساعدة"
    ]
    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    return markup

def areas_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("🌳 الغابة", callback_data="explore_forest"),
        types.InlineKeyboardButton("🕳️ الكهف", callback_data="explore_cave"),
        types.InlineKeyboardButton("🔥 النذر", callback_data="explore_nether"),
        types.InlineKeyboardButton("🌌 الإندر", callback_data="explore_end")
    ]
    markup.add(*buttons)
    return markup

# ============ أوامر البوت ============
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        player = Player(
            user_id=user_id,
            username=message.from_user.username or message.from_user.first_name
        )
        session.add(player)
        session.commit()
        
        welcome_text = """
🌟 *أهلاً بك في عالم ماينكرافت!*

أنا بوت المغامرات، سأساعدك في استكشاف عالم مليء بالمغامرات والموارد والأعداء!

🎮 ابدأ رحلتك الآن:
• استكشف المناطق المختلفة
• اجمع الموارد وصنع الأدوات
• واجه الأعداء وتطور
• ادخل المعبد لحل الألغاز
• هزم تنين الإندر لتصبح الأسطورة!

استخدم الأزرار أدناه للتنقل 👇
        """
    else:
        welcome_text = f"""
👋 *مرحباً بعودتك {player.username}!*

📊 *حالتك الحالية:*
• المستوى: {player.level} | الخبرة: {player.xp}/{player.level * 10}
• ❤️ الصحة: {player.current_health}/{player.max_health}
• 🍖 الجوع: {player.current_hunger}/{player.max_hunger}
• 🗺️ المنطقة: {player.current_area}
        """
    
    bot.send_message(
        message.chat.id, welcome_text,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "🌳 استكشاف الغابة")
def explore_forest_cmd(message):
    process_exploration(message, "forest")

@bot.message_handler(func=lambda msg: msg.text == "🕳️ استكشاف الكهف")
def explore_cave_cmd(message):
    process_exploration(message, "cave")

def process_exploration(message, area_name):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ يجب أن تبدأ اللعبة أولاً: /start")
        return
    
    result = game.explore_area(player, area_name)
    
    if "error" in result:
        bot.reply_to(message, f"❌ {result['error']}")
        return
    
    # بناء رسالة النتائج
    response = f"{result['emoji']} *استكشاف {result['area']}*\n\n"
    response += f"⏱️ وقت الاستكشاف: {result['explore_time']} ثانية\n\n"
    
    if result['rewards']:
        response += "🎁 *الموارد التي جمعتها:*\n"
        for reward in result['rewards']:
            response += f"• {reward}\n"
    
    if result.get('enemy'):
        enemy_data = result['enemy']
        response += f"\n⚔️ *واجهت {enemy_data['enemy_emoji']} {enemy_data['enemy_name']}!*\n"
        
        if enemy_data.get('victory'):
            response += "✅ انتصرت!\n"
            if enemy_data.get('drops'):
                response += "📦 *الغنائم:*\n"
                for drop in enemy_data['drops']:
                    response += f"• {drop}\n"
            response += f"⭐ خبرة: +{enemy_data['xp_reward']}\n"
        else:
            response += f"💔 خسرت {enemy_data.get('health_lost', 0)} صحة\n"
    
    if result.get('event'):
        response += f"\n🎲 *حدث:* {result['event']['message']}\n"
    
    response += f"\n⭐ *خبرة مكتسبة:* +{result['xp_gained']}\n"
    response += f"🍖 *الجوع:* {result['current_hunger']}/20\n"
    response += f"❤️ *الصحة:* {result['current_health']}/20\n"
    
    if result.get('starvation'):
        response += f"\n⚠️ {result['starvation']}"
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🏘️ الذهاب للقرية")
def village_menu(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        types.InlineKeyboardButton("🛒 المتجر", callback_data="village_shop"),
        types.InlineKeyboardButton("📋 المهام", callback_data="village_quests"),
        types.InlineKeyboardButton("😴 النوم", callback_data="village_sleep"),
        types.InlineKeyboardButton("📚 المكتبة", callback_data="village_library")
    ]
    markup.add(*buttons)
    
    bot.send_message(
        message.chat.id,
        "🏘️ *مرحباً بك في القرية!*\n\nماذا تريد أن تفعل؟",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == "🏛️ دخول المعبد")
def temple_start(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    result = game.explore_temple(player)
    
    if "error" in result:
        bot.reply_to(message, f"❌ {result['error']}")
        return
    
    response = f"🏛️ *{result['temple']}*\n\n"
    response += f"{result['message']}\n\n"
    response += f"*الغرفة 1:* {result['rooms'][0]['name']}\n"
    response += f"{result['rooms'][0]['description']}\n\n"
    
    # أزرار اختيار الباب
    markup = types.InlineKeyboardMarkup(row_width=3)
    for i in range(1, 4):
        markup.add(types.InlineKeyboardButton(f"باب {i}", callback_data=f"temple_1_{i}"))
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🎒 مخزوني")
def show_inventory(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    response = "🎒 *مخزونك (36 خانة):*\n\n"
    items_found = False
    
    for i in range(36):
        slot_key = f"slot_{i}"
        item = player.inventory.get(slot_key)
        if item:
            items_found = True
            response += f"{i+1}. {item['name']} x{item['amount']}\n"
    
    if not items_found:
        response += "📭 المخزون فارغ"
    
    response += f"\n\n🎽 *المعدات:*\n"
    for slot, item in player.equipment.items():
        response += f"• {slot}: {item if item else 'فارغ'}\n"
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "🛠️ التصنيع")
def crafting_menu(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for level in player.recipes_unlocked:
        level_name = level.replace("_", " ").title()
        markup.add(types.InlineKeyboardButton(
            f"📘 {level_name}",
            callback_data=f"craft_{level}"
        ))
    
    bot.send_message(
        message.chat.id,
        "🛠️ *قائمة التصنيع*\n\nاختر مستوى التصنيع:",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == "🍖 أكل")
def eat_menu(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    # جمع الأطعمة المتاحة
    foods = {}
    for slot_data in player.inventory.values():
        if slot_data and slot_data["name"] in ["apple", "bread", "cooked_beef", 
                "tropical_fruit", "honey", "raw_beef", "raw_chicken", "milk", "egg"]:
            foods[slot_data["name"]] = slot_data["amount"]
    
    if not foods:
        bot.reply_to(message, "🍖 ليس لديك أي طعام! استكشف الغابة للحصول على طعام")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for food, amount in foods.items():
        markup.add(types.InlineKeyboardButton(
            f"{food} (x{amount})",
            callback_data=f"eat_{food}"
        ))
    
    bot.send_message(
        message.chat.id,
        "🍖 *اختر الطعام الذي تريد تناوله:*",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == "❤️ حالتي")
def show_status(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    response = f"""
❤️ *حالة اللاعب*

👤 *الاسم:* {player.username}
⭐ *المستوى:* {player.level} ({player.xp}/{player.level * 10} XP)
🏅 *الألقاب:* {', '.join(player.titles) if player.titles else 'لا يوجد'}

❤️ *الصحة:* {'█' * player.current_health}{'░' * (player.max_health - player.current_health)} {player.current_health}/{player.max_health}
🍖 *الجوع:* {'█' * player.current_hunger}{'░' * (player.max_hunger - player.current_hunger)} {player.current_hunger}/{player.max_hunger}

🗺️ *المنطقة الحالية:* {player.current_area}
    """
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == "📊 مهاراتي")
def show_skills(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    response = f"""
📊 *مهاراتك*

🎯 *نقاط المهارة المتاحة:* {player.skill_points}

⚔️ *القوة:* {player.strength}/100 (+{int(player.strength * 2)}% ضرر)
💨 *السرعة:* {player.speed}/100 (-{int(player.speed * 5)}% وقت استكشاف)
💪 *التحمّل:* {player.endurance}/100 (+{player.endurance * 2} صحة قصوى)
🍀 *الحظ:* {player.luck}/100 (+{int(player.luck * 3)}% موارد نادرة)

🔓 *الوصفات المفتوحة:* {len(player.recipes_unlocked)} مستوى
    """
    
    if player.skill_points > 0:
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("⚔️ قوة", callback_data="skill_strength"),
            types.InlineKeyboardButton("💨 سرعة", callback_data="skill_speed"),
            types.InlineKeyboardButton("💪 تحمّل", callback_data="skill_endurance"),
            types.InlineKeyboardButton("🍀 حظ", callback_data="skill_luck")
        )
        bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(message.chat.id, response, parse_mode='Markdown')

# ============ معالجة الأزرار التفاعلية ============
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.answer_callback_query(call.id, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    data = call.data
    
    # استكشاف المناطق
    if data.startswith("explore_"):
        area = data.replace("explore_", "")
        process_exploration(call.message, area)
        bot.answer_callback_query(call.id, "تم الاستكشاف!")
    
    # المعبد
    elif data.startswith("temple_"):
        _, room, answer = data.split("_")
        result = game.solve_temple_puzzle(player, int(room), answer)
        
        if result.get("temple_complete"):
            bot.edit_message_text(
                f"🎉 *المعبد مكتمل!*\n\n{result['message']}",
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            bot.answer_callback_query(call.id, result['message'])
    
    # التصنيع
    elif data.startswith("craft_"):
        level = data.replace("craft_", "")
        recipes = CraftingSystem.get_recipes_by_level(level)
        
        response = f"🛠️ *وصفات {level.replace('_', ' ').title()}*\n\n"
        for recipe in recipes:
            response += f"• {recipe['emoji']} {recipe['name']}\n"
            response += f"  المتطلبات: {recipe['inputs']}\n"
            response += f"  الناتج: {recipe['output']}\n"
            response += f"  الخبرة: {recipe['xp']}\n\n"
        
        bot.edit_message_text(
            response,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    # تناول الطعام
    elif data.startswith("eat_"):
        food = data.replace("eat_", "")
        result = game.eat_food(player, food)
        
        if "error" in result:
            bot.answer_callback_query(call.id, result['error'])
        else:
            response = f"🍖 أكلت {food}!\n"
            response += f"🍖 شبع: +{result['hunger_restored']}\n"
            response += f"المستوى الحالي: {result['current_hunger']}/20\n"
            
            if result.get('effects'):
                for effect in result['effects']:
                    response += f"\n{effect}"
            
            bot.edit_message_text(
                response,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
    
    # نقاط المهارة
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
    
    # القرية - النوم
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
    
    # القرية - المتجر
    elif data == "village_shop":
        shop_text = """
🛒 *متجر القرية*

• 🍎 تفاح (2 خشب): 2 خشب بلوط
• 🥩 لحم مطبوخ (1 حديد): 1 سبيكة حديد
• ⛏️ معول حديدي (5 حديد): 5 سبائك حديد
• 🛡️ درع حديدي (15 حديد): 15 سبيكة حديد

استخدم الأمر: /buy [السلعة]
        """
        bot.edit_message_text(
            shop_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    # القرية - المهام
    elif data == "village_quests":
        quests = random.choice([
            {"name": "الفلاح العطشان", "description": "أحضر حليباً للفلاح", "reward": "خبز x3"},
            {"name": "الحداد المحتاج", "description": "أحضر 3 سبائك حديد", "reward": "سيف حديدي"},
            {"name": "الطفل الضائع", "description": "ابحث عن الطفل في الغابة", "reward": "تفاح ذهبي"}
        ])
        
        bot.edit_message_text(
            f"📋 *المهمة المتاحة:*\n\n*{quests['name']}*\n{quests['description']}\nالمكافأة: {quests['reward']}",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

# ============ أوامر إضافية ============
@bot.message_handler(commands=['dragon'])
def dragon_fight_cmd(message):
    user_id = message.from_user.id
    player = session.query(Player).filter_by(user_id=user_id).first()
    
    if not player:
        bot.reply_to(message, "❌ ابدأ اللعبة أولاً: /start")
        return
    
    result = game.start_dragon_fight(player)
    
    if "error" in result:
        bot.reply_to(message, f"❌ {result['error']}")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for i in range(1, 5):
        markup.add(types.InlineKeyboardButton(
            f"مكان {i}", callback_data=f"dragon_1_{i}"
        ))
    
    bot.send_message(
        message.chat.id,
        f"🐉 *{result['boss']}*\n\n*المرحلة 1:* {result['phase_name']}\n{result['description']}",
        parse_mode='Markdown',
        reply_markup=markup
    )

@bot.message_handler(commands=['event'])
def world_event_cmd(message):
    # أمر للمشرفين فقط - تفعيل حدث عالمي
    result = game.trigger_world_event()
    
    bot.send_message(
        message.chat.id,
        f"{result['message']}\n\n⏱️ المدة: {result['duration']} ساعة",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = """
🎮 *أوامر البوت:*

/start - بدء اللعبة
/inventory - عرض المخزون
/craft - فتح قائمة التصنيع
/status - عرض حالتك
/skills - عرض مهاراتك
/eat - تناول الطعام
/dragon - بدء معركة التنين
/help - هذه المساعدة

استخدم الأزرار في الأسفل للتنقل السهل!
    """
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# ============ تشغيل البوت ============
if __name__ == "__main__":
    print("🤖 بوت ماينكرافت يعمل الآن...")
    bot.infinity_polling()
