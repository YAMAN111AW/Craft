"""
ملف ترحيل قاعدة البيانات - شغله مرة واحدة فقط لتحديث هيكل القاعدة
python migrate_database.py
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import json

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///minecraft_bot.db')

if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DATABASE_URL)

def migrate_database():
    """ترحيل قاعدة البيانات بأمان"""
    with engine.connect() as conn:
        print("🔍 فحص قاعدة البيانات...")
        
        # 1. إضافة أعمدة جديدة إذا لم تكن موجودة
        try:
            conn.execute(text("""
                ALTER TABLE players 
                ADD COLUMN IF NOT EXISTS user_id_new VARCHAR
            """))
            print("✅ تم إضافة عمود user_id_new")
        except Exception as e:
            print(f"⚠️ عمود user_id_new موجود مسبقاً: {e}")
        
        try:
            conn.execute(text("""
                ALTER TABLE players 
                ADD COLUMN IF NOT EXISTS dragon_crystals INTEGER DEFAULT 6
            """))
            print("✅ تم إضافة عمود dragon_crystals")
        except:
            pass
        
        try:
            conn.execute(text("""
                ALTER TABLE players 
                ADD COLUMN IF NOT EXISTS dragon_sword_hits INTEGER DEFAULT 0
            """))
            print("✅ تم إضافة عمود dragon_sword_hits")
        except:
            pass
        
        try:
            conn.execute(text("""
                ALTER TABLE players 
                ADD COLUMN IF NOT EXISTS final_blows INTEGER DEFAULT 0
            """))
            print("✅ تم إضافة عمود final_blows")
        except:
            pass
        
        # 2. نسخ البيانات من user_id القديم إلى الجديد
        try:
            result = conn.execute(text("""
                UPDATE players 
                SET user_id_new = CAST(user_id AS VARCHAR)
                WHERE user_id_new IS NULL
            """))
            print(f"✅ تم ترحيل {result.rowcount} لاعب")
        except Exception as e:
            print(f"⚠️ خطأ في ترحيل user_id: {e}")
        
        # 3. التحقق من البيانات النصية وتحويلها
        result = conn.execute(text("SELECT id, inventory, equipment, status_effects, titles, recipes_unlocked FROM players"))
        
        for row in result:
            player_id = row[0]
            updates = []
            
            # التحقق من inventory
            if row[1] and isinstance(row[1], dict):
                updates.append(f"inventory = '{json.dumps(row[1])}'")
            
            # التحقق من equipment
            if row[2] and isinstance(row[2], dict):
                updates.append(f"equipment = '{json.dumps(row[2])}'")
            
            # التحقق من status_effects
            if row[3] and isinstance(row[3], list):
                updates.append(f"status_effects = '{json.dumps(row[3])}'")
            
            # التحقق من titles
            if row[4] and isinstance(row[4], list):
                updates.append(f"titles = '{json.dumps(row[4])}'")
            
            # التحقق من recipes_unlocked
            if row[5] and isinstance(row[5], list):
                updates.append(f"recipes_unlocked = '{json.dumps(row[5])}'")
            
            if updates:
                update_query = f"UPDATE players SET {', '.join(updates)} WHERE id = {player_id}"
                try:
                    conn.execute(text(update_query))
                    print(f"✅ تم تحديث اللاعب {player_id}")
                except Exception as e:
                    print(f"⚠️ خطأ في تحديث اللاعب {player_id}: {e}")
        
        conn.commit()
        print("\n🎉 تم الترحيل بنجاح!")

if __name__ == "__main__":
    migrate_database()
