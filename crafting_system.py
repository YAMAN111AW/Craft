class CraftingSystem:
    RECIPES = {
        "level_1": [
            {"name":"ألواح خشب","emoji":"🪵","in":{"oak_wood":1},"out":{"wooden_planks":4},"xp":1},
            {"name":"عصي","emoji":"🥢","in":{"wooden_planks":2},"out":{"sticks":4},"xp":1},
            {"name":"طاولة تصنيع","emoji":"🔨","in":{"wooden_planks":4},"out":{"crafting_table":1},"xp":2},
            {"name":"فرن","emoji":"🔥","in":{"stone":8},"out":{"furnace":1},"xp":2},
            {"name":"سياج","emoji":"🚧","in":{"sticks":6},"out":{"fence":3},"xp":1},
            {"name":"باب خشبي","emoji":"🚪","in":{"wooden_planks":6},"out":{"wooden_door":1},"xp":2},
        ],
        "level_2": [
            {"name":"فأس خشبي","emoji":"🪓","in":{"wooden_planks":3,"sticks":2},"out":{"wooden_axe":1},"xp":3},
            {"name":"معول خشبي","emoji":"⛏️","in":{"wooden_planks":3,"sticks":2},"out":{"wooden_pickaxe":1},"xp":3},
            {"name":"سيف خشبي","emoji":"🗡️","in":{"wooden_planks":2,"sticks":1},"out":{"wooden_sword":1},"xp":3},
            {"name":"قوس","emoji":"🏹","in":{"sticks":3,"spider_silk":3},"out":{"bow":1},"xp":4},
            {"name":"سهام x8","emoji":"🏹","in":{"sticks":1,"feather":1,"stone":1},"out":{"arrows":8},"xp":2},
            {"name":"خبز","emoji":"🍞","in":{"wheat":3},"out":{"bread":1},"xp":2},
        ],
        "level_3": [
            {"name":"فأس حجري","emoji":"🪓","in":{"stone":3,"sticks":2},"out":{"stone_axe":1},"xp":5},
            {"name":"سيف حجري","emoji":"🗡️","in":{"stone":2,"sticks":1},"out":{"stone_sword":1},"xp":5},
            {"name":"معول حديدي","emoji":"⛏️","in":{"iron_ore":3,"sticks":2},"out":{"iron_pickaxe":1},"xp":7},
            {"name":"درع حديدي","emoji":"🛡️","in":{"iron_ore":8},"out":{"iron_chestplate":1},"xp":8},
            {"name":"شعلة x4","emoji":"🔦","in":{"coal":1,"sticks":1},"out":{"torch":4},"xp":2},
            {"name":"سرج","emoji":"🐴","in":{"leather":5,"iron_ore":2},"out":{"saddle":1},"xp":10},
        ],
        "level_4": [
            {"name":"سيف حديدي","emoji":"🗡️","in":{"iron_ore":2,"sticks":1},"out":{"iron_sword":1},"xp":8},
            {"name":"فأس ألماسي","emoji":"🪓","in":{"diamond":3,"sticks":2},"out":{"diamond_axe":1},"xp":12},
            {"name":"تفاح ذهبي","emoji":"🍎","in":{"apple":1,"gold_ore":8},"out":{"golden_apple":1},"xp":15},
            {"name":"جرعة شفاء","emoji":"🧪","in":{"sap":2,"mushroom":1},"out":{"healing_potion":1},"xp":8},
            {"name":"بوصلة","emoji":"🧭","in":{"iron_ore":4},"out":{"compass":1},"xp":5},
        ],
        "level_5": [
            {"name":"سيف ألماسي","emoji":"🗡️","in":{"diamond":2,"sticks":1},"out":{"diamond_sword":1},"xp":15},
            {"name":"درع ناري","emoji":"🔥","in":{"fiery_coal":5,"iron_ore":8},"out":{"fire_chestplate":1},"xp":18},
            {"name":"بوابة النذر","emoji":"🔥","in":{"obsidian":10},"out":{"nether_portal":1},"xp":20},
            {"name":"عين الإندر","emoji":"👁️","in":{"ender_pearl":1,"blaze_rod":1},"out":{"eye_of_ender":1},"xp":10},
            {"name":"سيف الإندر","emoji":"⚔️","in":{"diamond_sword":1,"ender_pearl":5},"out":{"ender_sword":1},"xp":30},
            {"name":"جناح طيران","emoji":"🪽","in":{"diamond":1,"feather":10},"out":{"elytra":1},"xp":25},
        ]
    }

    @classmethod
    def get_recipes(cls, player):
        all_recipes = []
        recipes_list = player.recipes_unlocked if isinstance(player.recipes_unlocked, list) else player.recipes_unlocked
        for level in recipes_list:
            if level in cls.RECIPES:
                all_recipes.extend(cls.RECIPES[level])
        return all_recipes

    @classmethod
    def can_craft(cls, player, recipe):
        for item, amt in recipe["in"].items():
            if not player.has_item(item, amt):
                return False, f"تحتاج {amt} {item}"
        return True, "يمكنك التصنيع"

    @classmethod
    def craft(cls, player, recipe):
        ok, msg = cls.can_craft(player, recipe)
        if not ok:
            return False, msg
        
        for item, amt in recipe["in"].items():
            player.remove_item(item, amt)
        
        for item, amt in recipe["out"].items():
            player.add_item(item, amt)
        
        player.add_xp(recipe["xp"])
        return True, f"✅ تم تصنيع {recipe['name']}!"
