import json
import copy
import random
import re
import ast
from openai import OpenAI
import os
from apikey import openai_apikey
from tqdm import tqdm


def split_queries_random_pick(data):
    for i, d in enumerate(data):
        queries_raw = d['query']
        queries = re.split(r'\s*\n\s*|\s*\n\s*\n\s*', queries_raw.strip())
        assert len(queries) == 5

        data[i]['query_all'] = queries
        data[i]['query_selected'] = queries[random.randint(0, 4)]
    return data


def check_food_names(r, key='query_selected'):
    if r[key] == "-1":
        return True
    if isinstance(r['description'], list):
        food_names = r['description']
    else:
        food_names = ast.literal_eval(r['description'])
    for food_idx, food_name in enumerate(food_names):
        # check if any word in the food name is in the query
        candidates = re.split(r'[,\s()]+', food_name)
        length = len(candidates)
        for i in range(length):
            # avoid plural form
            if candidates[i].endswith('s'):
                candidates.append(candidates[i][:-1])
            if candidates[i].endswith('es'):
                candidates.append(candidates[i][:-2])
            if candidates[i].endswith('ies'):
                candidates.append(candidates[i][:-3]+'y')
        # special cases
        if food_name == 'Hard candy' and 'lollipop' in ast.literal_eval(r['unit'])[food_idx]:
            candidates.append('lollipop')
        elif food_name == 'Gumdrops' and 'gummy' in ast.literal_eval(r['unit'])[food_idx]:
            candidates.append('gummy')
        elif food_name == 'Licorice' and 'Twizzler Bite' in ast.literal_eval(r['unit'])[food_idx]:
            candidates.append('Bite')
        elif food_name == 'Bread, French or Vienna' and 'baguette' in ast.literal_eval(r['unit'])[food_idx]:
            candidates.append('baguette')
        elif food_name == 'Fruit juice drink, with high vitamin C' and 'Jammers ' in ast.literal_eval(r['unit'])[food_idx]:
            candidates.append('Jammers ')
        elif food_name == 'Cordial or liqueur':
            candidates.append('Cordials')
        elif food_name == 'Spanakopitta':
            candidates.append('Spanakopita')
        elif food_name == 'Bread, chappatti or roti':
            candidates.append('chapatti')


        words = re.findall(r'\b\w+\b', r[key].lower())

        if any(candidate.lower() in words for candidate in candidates):
            pass
        else:
            return False
    return True
        
    
def check_food_units(r, client, key='query_pass_food_name_check'):
    '''
    Ask GPT to check if the food unit is included in the query
    '''
    prompt = '''
        Determine if the unit of the "Food Item" in the given sentence matches the "Desired Unit." If it matches, respond only with the exact phrase from the sentence that describes the unit, including any articles, without food name. If it does not match, respond with -1.
        Food Item: {food_name}
        Desired Unit: {unit}
        Sentence: {sentence}
    '''

    if isinstance(r['description'], list):
        food_names = r['description']
    else:
        food_names = ast.literal_eval(r['description'])
    if isinstance(r['unit'], list):
        units = r['unit']
    else:
        units = ast.literal_eval(r['unit'])
    assert len(units) == len(food_names)

    real_units = []
    sucess = True
    for food_idx, food_name in enumerate(food_names):
        unit = units[food_idx]
        query = prompt.format(food_name=food_name, unit=unit, sentence=r[key])
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": query
                }
            ]
        )
        real_unit = completion.choices[0].message.content
        real_units.append(real_unit)
        if real_unit == '-1':
            sucess = False
        # check if the real unit is in the query
        real_unit_words = re.findall(r'\b\w+\b', real_unit.lower())
        words = re.findall(r'\b\w+\b', r[key].lower())
        if all(word in words for word in real_unit_words):
            pass
        else:
            sucess = False
    return sucess, real_units


def improve_food_name(r, client):
    '''
    Ask GPT to improve the food name
    '''
    prompt = '''
        For the given food item along with their serving size and eating occasion, create a meal description, mimicking natural language. You will also receive a base description that should be enhanced to include all the food items from the provided list. Here is one example:
        Example input- Food list: {{"description": ["Breakfast tart, lowfat", "Cereal (General Mills Lucky Charms)", "Milk, whole", "Apple juice, 100%"], "unit": ["1 Pop Tart", "1 prepackaged bowl", "1 cup", "1 individual school container"], "eating_occasion": "Breakfast"}}
        Example input- Base description: For breakfast, I had a low-fat breakfast tart, a cup of whole milk, and an individual school container of apple juice.
        Example output- For breakfast, I had a low-fat breakfast tart, a prepackaged bowl of General Mills Lucky Charms cereal, a cup of whole milk, and an individual school container of apple juice.
                    
        Food list: {food_list}
        Base Sentence: {sentence}
    '''
    food_list = {}
    food_list['description'] = r['description']
    food_list['unit'] = r['unit']
    food_list['eating_occasion'] = r['eating_occasion']
    
    query = prompt.format(food_list=food_list, sentence=r['query_selected'])
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": query
            }
        ]
    )
    updated_sentence = completion.choices[0].message.content
    return updated_sentence


def improve_food_unit(r, client):
    '''
    Ask GPT to improve the food name
    '''
    prompt = '''
        For the given food item along with their serving size and eating occasion, create a meal description, mimicking natural language. You will also receive a base description that should be enhanced to include all the food units from the provided list. Here is one example:
        Example input- Food list: {{"description": ["Breakfast tart, lowfat", "Cereal (General Mills Lucky Charms)", "Milk, whole", "Apple juice, 100%"], "unit": ["1 Pop Tart", "1 prepackaged bowl", "1 cup", "1 individual school container"], "eating_occasion": "Breakfast"}}
        Example input- For breakfast, I had a low-fat breakfast tart, a prepackaged bowl of General Mills Lucky Charms cereal, a cup of whole milk, and some apple juice.
        Example output- For breakfast, I had a low-fat breakfast tart, a prepackaged bowl of General Mills Lucky Charms cereal, a cup of whole milk, and an individual school container of apple juice.

        Food list: {food_list}
        Base Sentence: {sentence}
    '''
    food_list = {}
    food_list['description'] = r['description']
    food_list['unit'] = r['unit']
    food_list['eating_occasion'] = r['eating_occasion']
    
    query = prompt.format(food_list=food_list, sentence=r['query_pass_food_name_check'])
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {
                "role": "user",
                "content": query
            }
        ]
    )
    updated_sentence = completion.choices[0].message.content
    return updated_sentence
    


if __name__ == '__main__':
    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # automatic check food names

    # random.seed(0)
    # os.environ["OPENAI_API_KEY"] = openai_apikey
    # client = OpenAI()

    # with open('/home/andong/NutriBench_FT/benchmark/query/meal_natural_query.json') as f:
    #     res = json.load(f)
    # res_new = copy.deepcopy(res)
    # res_new = split_queries_random_pick(res_new)

    # # check food names are included
    # fail_count_before_regenerate = 0
    # fail_count_after_regenerate = 0
    # for i, r in tqdm(enumerate(res_new)):
    #     if not check_food_names(r):
    #         # try to change query in query_all
    #         done = False
    #         for q in r['query_all']:
    #             r['query_selected'] = q
    #             if check_food_names(r):
    #                 done = True
    #                 break
    #         if not done:
    #             fail_count_before_regenerate += 1
    #             query_regenerated = improve_food_name(r, client)
    #             r['query_selected'] = query_regenerated
    #             if check_food_names(r):
    #                 r['query_pass_food_name_check'] = r['query_selected']
    #             else:
    #                 fail_count_after_regenerate += 1
    #                 r['query_pass_food_name_check'] = ""
    #                 print(i)
    #                 print(r['description'])
    #                 print(r['unit'])
    #                 print(r['query_selected'])
    #         else:
    #             r['query_pass_food_name_check'] = r['query_selected']
    #     else:
    #         r['query_pass_food_name_check'] = r['query_selected']
    # print("fail_count_before_regenerate: ", fail_count_before_regenerate)
    # print("fail_count_after_regenerate: ", fail_count_after_regenerate)

    # with open('/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_v1.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #

    # manually check the remaining food items
    # path = '/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_v1.json'
    # with open(path) as f:
    #     res = json.load(f)
    # res_new = copy.deepcopy(res)

    # res_new[2171]['query_pass_food_name_check'] = res_new[2171]['query_selected']
    # res_new[2553]['query_pass_food_name_check'] = res_new[2553]['query_selected']
    # res_new[3861]['query_pass_food_name_check'] = 'For breakfast this morning, I enjoyed a delicious slice of toasted whole wheat bread, paired with a boiled egg. I savored a steaming cup of herbal tea sweetened with a tbsp of honey, while also relishing a can of sardines, drained and flavorful. To round off my meal, I added a cup of tap water and a cube of rich Cheddar cheese for a delightful finish.'
    # res_new[4786]['query_pass_food_name_check'] = res_new[4786]['query_selected']
    # res_new[7073]['query_pass_food_name_check'] = res_new[7073]['query_selected']

    # c = 0
    # for i, r in enumerate(res_new):
    #     if r['query_pass_food_name_check'] == "" or not check_food_names(r, key='query_pass_food_name_check'):
    #         c += 1
    #         print(i)
    #         print(r['description'])
    #         print(r['unit'])
    #         print(r['query_pass_food_name_check'])
    #         print('-'*100)
    # assert c == 0
    # print('-'*100)
    # print('Pass food name check')
    # print('-'*100)

    # with open('/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_v2.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # automatic check food units
    # random.seed(0)
    # os.environ["OPENAI_API_KEY"] = openai_apikey
    # client = OpenAI()

    # path = '/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_v2.json'
    # with open(path) as f:
    #     res = json.load(f)
    # res_new = copy.deepcopy(res)

    # fail_count_before_regenerate = 0
    # fail_count_after_regenerate = 0
    # for i, r in tqdm(enumerate(res_new)):
    #     sucess, real_units = check_food_units(r, client)
    #     r['unit_in_query'] = real_units
    #     if not sucess:
    #         # automatic improve the food unit
    #         fail_count_before_regenerate += 1
    #         query_regenerated = improve_food_unit(r, client)
    #         r['query_regenerated_for_unit'] = query_regenerated
    #         sucess_, real_units_ = check_food_units(r, client, key='query_regenerated_for_unit')
    #         r['unit_in_query_regenerated_for_unit'] = real_units_
    #         if sucess_:
    #             r['query_processed'] = r['query_regenerated_for_unit']
    #         else:
    #             fail_count_after_regenerate += 1
    #             print(i)
    #             print(r['description'])
    #             print(r['unit'])
    #             print(r['query_pass_food_name_check'])
    #             print(real_units)
    #             print(r['query_regenerated_for_unit'])
    #             print(real_units_)
    #             print('-'*100)
    #             r['query_processed'] = ""
    #     else:
    #         r['query_regenerated_for_unit'] = ""
    #         r['unit_in_query_regenerated_for_unit'] = ""
    #         r['query_processed'] = r['query_pass_food_name_check']

    # print("fail_count_before_regenerate: ", fail_count_before_regenerate)
    # print("fail_count_after_regenerate: ", fail_count_after_regenerate)
    
    # with open('/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_v3.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # manually check the remaining food items

    path = '/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_v3.json'
    with open(path) as f:
        res = json.load(f)
    res_new = copy.deepcopy(res)

    fail_count = len([r for r in res_new if r['query_processed'] == ""])
    print(fail_count)

    # manual modification
    res_new[118]['query_processed'] = "-1"
    res_new[224]['query_processed'] = "For breakfast, I enjoyed a McDonald's low-fat yogurt parfait with fruit, sweetened with an individual packet of white granulated sugar, and complemented it with a medium cup of brewed decaffeinated coffee with one fl oz of half and half."
    res_new[335]['query_processed'] = "For breakfast today, I savored a warm egg and cheese sandwich on a biscuit, complemented by a cup of coffee with 1 fl oz flavored creamer, a cup of water, a sweet banana, and a lovely fresh peach."
    res_new[369]['query_processed'] = "For dinner, I feasted on a Whopper cheese burger, washed down with a 12 fl oz can of fruit-flavored soft drink, and enjoyed a small side of French fries from the fast food place."
    res_new[374]['query_processed'] = "During my afternoon break, I enjoyed a medium butter or sugar cookie paired with a small refreshing cup of hot green tea."
    res_new[403]['query_processed'] = "During my lunch, I savored a hot dog bun filled with a delicious bun-size Italian sausage, complemented by a small serving of lightly salted potato chips and washed down with a refreshing 12 fl oz bottle of unsweetened water."
    res_new[419]['query_processed'] = "During snack time, I enjoyed a delicious small apple, a raw banana, and two breakfast tarts."
    res_new[437]['query_processed'] = "For a satisfying snack, I indulged in a meal replacement bar, complemented by a mini microwave bag of light butter popcorn and a chewy Fiber One granola bar."
    res_new[441]['query_processed'] = "For lunch, I treated myself to a satisfying Steak and cheese submarine sandwich, alongside a succulent raw pear and a refreshing 10 fl oz bottle of apple juice."
    res_new[478]['query_processed'] = "For my dinner, I treated myself to a caffeine-free fruit-flavored soft drink in a child/senior drink size, a classic cheeseburger from McDonald's, and a kids meal portion of french fries."
    res_new[538]['query_processed'] = "For dinner, I savored a child-friendly fruit juice drink loaded with vitamin C, paired with a McDonald's cheeseburger and a kids meal order of fast food french fries."
    res_new[568]['query_processed'] = "For a delightful snack, I savored a medium chocolate-iced butter cookie alongside a Clif Kids Organic Zbar to keep me fueled."
    res_new[576]['query_processed'] = "For a quick snack, I reached for a bottle of water, savoring it with a large chocolate sandwich cookie and a small chocolate chip cookie bar for a sweet finish."
    res_new[607]['query_processed'] = "This morning, I enjoyed a 12 fl oz can of diet cola paired with a raw banana."
    res_new[696]['query_processed'] = "For breakfast, I had a delicious Toaster Strudel Danish pastry filled with fruit, accompanied by a cup of reduced-fat (2%) milk."
    res_new[707]['query_processed'] = "During my snack time, I had a juicy raw orange paired with a raw banana and washed it down with a cup of bottled water."
    res_new[715]['query_processed'] = "For breakfast, I started my day with a cup of tap water, a fresh orange, a raw banana, and a small apple."
    res_new[752]['query_processed'] = "I treated myself to a snack of a frankfurter on a plain white bun, garnished with a tbsp of mustard and a tbsp of ketchup, along with a small single serving bag of potato chips and a chilled can of diet cola."
    res_new[770]['query_processed'] = "I started my day with a serving of apple juice from an individual school container and relished half a thick-crust pizza featuring meat toppings, excluding pepperoni."
    res_new[881]['query_processed'] = "At breakfast time, I enjoyed a bar of General Mills Nature Valley Crunchy Granola, a cup of whole milk, and a raw plum."
    res_new[884]['query_processed'] = "My snack consisted of a single serving bag of Doritos nacho cheese chips complemented by a raw banana."
    res_new[929]['query_processed'] = "For lunch, I had a small white hoagie roll filled with a cup of ham and barbecue sauce, paired with a cup of bottled unsweetened water."
    res_new[937]['query_processed'] = "For a quick snack, I savored a medium iced latte flavored coffee, paired with a cup of creamy whole milk yogurt and a juicy medium plum."
    res_new[942]['query_processed'] = "I started my day with a delightful Pop Tart, 1 fl oz of fat-free milk, and a full cup of freshly brewed coffee."
    res_new[1036]['query_processed'] = "For my dinner, I had a Hot Pockets Philly Steak and Cheese turnover with no gravy, complemented by a 12 fl oz can of fruit-flavored soft drink."
    res_new[1057]['query_processed'] = res_new[1057]['query_pass_food_name_check']
    res_new[1068]['query_processed'] = res_new[1068]['query_pass_food_name_check']
    res_new[1077]['query_processed'] = "For dinner, I treated myself to a vanilla ice cream sandwich, enjoyed a fun-size SNICKERS bar for a sweet touch, and washed it all down with a 20 fl oz bottle of caffeine-free fruit-flavored soft drink. To round out the meal, I had a medium burrito filled with meat and another medium burrito loaded with chicken and sour cream."
    res_new[1092]['query_processed'] = res_new[1092]['query_pass_food_name_check']
    res_new[1121]['query_processed'] = res_new[1121]['query_pass_food_name_check']
    res_new[1130]['query_processed'] = res_new[1130]['query_pass_food_name_check']
    res_new[1145]['query_processed'] = res_new[1145]['query_pass_food_name_check']
    res_new[1147]['query_processed'] = res_new[1147]['query_pass_food_name_check']
    res_new[1153]['query_processed'] = "I savored a chicken fillet biscuit sandwich from a fast food joint for breakfast, accompanied by a 20 fl oz bottle of cola."
    res_new[1159]['query_processed'] = res_new[1159]['query_pass_food_name_check']
    res_new[1175]['query_processed'] = res_new[1175]['query_pass_food_name_check']
    res_new[1196]['query_processed'] = res_new[1196]['query_pass_food_name_check']
    res_new[1197]['query_processed'] = res_new[1197]['query_pass_food_name_check']
    res_new[1201]['query_processed'] = res_new[1201]['query_pass_food_name_check']
    res_new[1216]['query_processed'] = "This morning, my breakfast consisted of a large brewed coffee, enhanced with an individual container of flavored half and half cream, and I couldn't resist having a whole banana on the side."
    res_new[1231]['query_processed'] = "At dinner, I treated myself to a refreshing 12 fl oz can of fruit-flavored soft drink and a satisfying meatless cheese enchilada."
    res_new[1234]['query_processed'] = res_new[1234]['query_pass_food_name_check']
    res_new[1238]['query_processed'] = res_new[1238]['query_pass_food_name_check']
    res_new[1277]['query_processed'] = "For lunch, I indulged in an orange, paired with a delightful chocolate-covered marshmallow cookie and a medium-sized brewed coffee."
    res_new[1284]['query_processed'] = res_new[1284]['query_pass_food_name_check']
    res_new[1285]['query_processed'] = res_new[1285]['query_pass_food_name_check']
    res_new[1295]['query_processed'] = res_new[1295]['query_pass_food_name_check']
    res_new[1310]['query_processed'] = res_new[1310]['query_pass_food_name_check']
    res_new[1323]['query_processed'] = res_new[1323]['query_pass_food_name_check']
    res_new[1339]['query_processed'] = res_new[1339]['query_pass_food_name_check']
    res_new[1340]['query_processed'] = res_new[1340]['query_pass_food_name_check']
    res_new[1349]['query_processed'] = res_new[1349]['query_pass_food_name_check']
    res_new[1390]['query_processed'] = res_new[1390]['query_pass_food_name_check']
    res_new[1393]['query_processed'] = res_new[1393]['query_pass_food_name_check']
    res_new[1403]['query_processed'] = "To start my day, I indulged in a small marshmallow cookie bar with rice cereal and chocolate chips, complemented by a package of two breakfast tarts."
    res_new[1405]['query_processed'] = res_new[1405]['query_pass_food_name_check']
    res_new[1413]['query_processed'] = res_new[1413]['query_pass_food_name_check']
    res_new[1443]['query_processed'] = res_new[1443]['query_pass_food_name_check']
    res_new[1479]['query_processed'] = res_new[1479]['query_pass_food_name_check']
    res_new[1481]['query_processed'] = res_new[1481]['query_pass_food_name_check']
    res_new[1496]['query_processed'] = res_new[1496]['query_pass_food_name_check']
    res_new[1503]['query_processed'] = res_new[1503]['query_pass_food_name_check']
    res_new[1545]['query_processed'] = res_new[1545]['query_pass_food_name_check']
    res_new[1546]['query_processed'] = res_new[1546]['query_pass_food_name_check']
    res_new[1640]['query_processed'] = res_new[1640]['query_pass_food_name_check']
    res_new[1641]['query_processed'] = res_new[1641]['query_pass_food_name_check']
    res_new[1642]['query_processed'] = "This morning, my breakfast included a tasty breakfast tart, an individual school carton of refreshing orange juice, a cup of whole chocolate milk, and a cup of General Mills Cocoa Puffs cereal."
    res_new[1652]['query_processed'] = "During lunch, I had a piece of tasty medium crust pepperoni pizza and washed it down with a carton of 100% orange juice."
    res_new[1668]['query_processed'] = res_new[1668]['query_pass_food_name_check']
    res_new[1669]['query_processed'] = res_new[1669]['query_pass_food_name_check']
    res_new[1671]['query_processed'] = res_new[1671]['query_pass_food_name_check']
    res_new[1674]['query_processed'] = res_new[1674]['query_pass_food_name_check']
    res_new[1675]['query_processed'] = res_new[1675]['query_pass_food_name_check']
    res_new[1686]['query_processed'] = res_new[1686]['query_pass_food_name_check']
    res_new[1700]['query_processed'] = res_new[1700]['query_pass_food_name_check']
    res_new[1810]['query_processed'] = "This morning, I enjoyed a small brewed coffee with one fl oz of half and half, paired with a delicious large fruit muffin."
    res_new[1871]['query_processed'] = "For my breakfast, I had a delicious English muffin slathered with a tablespoon of butter, complemented by a cup of brewed coffee with one fl oz of half and half."
    res_new[1876]['query_processed'] = "During my afternoon snack, I enjoyed a 12 fl oz can of diet cola alongside a raw banana."
    res_new[1880]['query_processed'] = "At dinner, I enjoyed a medium bolillo roll paired with a comforting cup of instant coffee."
    res_new[1921]['query_processed'] = "For dinner, I relished a large portion of French fries from the drive-thru and a small patty cheeseburger that hit the spot."
    res_new[1924]['query_processed'] = res_new[1924]['query_pass_food_name_check']
    res_new[1928]['query_processed'] = res_new[1928]['query_pass_food_name_check']
    res_new[1933]['query_processed'] = "I kicked off my day with a delightful breakfast of one pouch of pancakes from frozen, complemented by a tablespoon of rich pancake syrup."
    res_new[1981]['query_processed'] = "-1"
    res_new[1990]['query_processed'] = "I started my day with a 5.3 oz serving of Greek yogurt made from whole milk, topped with fruit, and I complemented it with a raw banana."
    res_new[2031]['query_processed'] = res_new[2031]['query_pass_food_name_check']
    res_new[2037]['query_processed'] = res_new[2037]['query_pass_food_name_check']
    res_new[2064]['query_processed'] = "My snack consisted of a 1-inch stack of plain potato chips and one medium single serving of other flavored potato chips, and I rounded it off with a delicious 3 MUSKETEERS Bar and a nice can of fruit-flavored soft drink."
    res_new[2082]['query_processed'] = "This morning, I enjoyed a refreshing 16.9 fl oz bottle of unsweetened water alongside a juicy raw tangerine."
    res_new[2090]['query_processed'] = "I treated myself to a juicy raw pear and complemented it with a small single serving bag of savory flavored potato chips for my snack."
    res_new[2105]['query_processed'] = "This morning, I enjoyed a sunny-side-up egg along with a scrambled egg white omelet, paired with a hearty cup of vegetable-enhanced spaghetti sauce."
    res_new[2107]['query_processed'] = "My afternoon snack consisted of a small marshmallow and peanut butter cookie, complemented by a Capri Sun fruit juice pouch and a small chocolate chip cookie for a sweet finish."
    res_new[2116]['query_processed'] = "For a quick snack, I grabbed a tangerine and complemented it with a medium oatmeal cookie packed with raisins."
    res_new[2120]['query_processed'] = "I savored a bite-sized sweet chocolate along with a perfectly raw banana during my snack break."
    res_new[2126]['query_processed'] = "This morning, I enjoyed a delicious peanut butter sandwich cookie, complemented by a refreshing cup of bottled water and a Kellogg's Nutri-Grain cereal bar."
    res_new[2129]['query_processed'] = "Tonight's dinner consisted of a delicious cheeseburger on a white bun with a medium patty, slathered with a tablespoon ketchup and a packet mustard. I also indulged in a beef frankfurter, enhanced with a packet of hot pepper sauce for an extra kick."
    res_new[2133]['query_processed'] = "At dinner, I savored a Quarter Pounder cheeseburger from McDonald's along with a large serving of french fries and a small iced tea that was sweetened just right."
    res_new[2171]['query_processed'] = "For my snack, I treated myself to a piece of creamy truffle, a medium wedge of refreshing honeydew melon, and a deliciously ripe strawberry to balance the flavors."
    res_new[2176]['query_processed'] = "I enjoyed a fluffy yeast doughnut paired with a hearty cheeseburger from McDonald's for my lunch today."
    res_new[2202]['query_processed'] = "To start my day, I had an 8 fl oz bottle of orange juice with calcium, a 16.9 fl oz bottle of unsweetened water, and a sweet yeast doughnut."
    res_new[2212]['query_processed'] = "During snack time, I treated myself to a sicle of delightful fudgesicle, complemented by a juicy raw peach and a chewy piece of fruit snacks candy."
    res_new[2229]['query_processed'] = "For my breakfast, I enjoyed a savory chicken fillet biscuit from a fast food restaurant, complemented by a cup of cool unsweetened bottled water."
    res_new[2284]['query_processed'] = "During my snack time, I treated myself to a classic Twinkie snack cake and paired it with a medium bar of marshmallow cookie, which was soft and chewy."
    res_new[2295]['query_processed'] = "I started my day with a delicious egg omelet made with oil and a 6.75 fl oz serving of apple juice."
    res_new[2318]['query_processed'] = "For a quick snack, I grabbed a Clif Kids Organic Zbar and washed it down with a bottle of unsweetened water."
    res_new[2321]['query_processed'] = "This morning, I enjoyed a delicious medium sweet roll and paired it with a fresh, raw banana."
    res_new[2325]['query_processed'] = "For a cozy snack, I had a delightful peanut butter sandwich cookie paired with a small hot herbal tea."
    res_new[2329]['query_processed'] = "At lunchtime, I enjoyed a medium single serving of flavored reduced fat tortilla chips, complemented by a cup of refreshing low-fat strawberry milk and a juicy raw peach."
    res_new[2343]['query_processed'] = "This morning, I enjoyed a Little Debbie sweet cinnamon bun with frosting from Little Debbie, paired with a refreshing bottle of unsweetened water."
    res_new[2357]['query_processed'] = "During my lunch break, I enjoyed a piece of delicious medium crust cheese pizza from school, paired with a refreshing cup of chocolate milk and a crisp medium apple."
    res_new[2383]['query_processed'] = "I started my day with a slice of whole wheat bread, a delicious clementine, a tube of yogurt made with low-fat milk and fruit, and a slice of cheddar cheese."
    res_new[2403]['query_processed'] = "For my dinner, I had a delicious Quarter Pounder cheeseburger, washed down with a refreshing 16.9 fl oz bottle of unsweetened water, alongside a large order of crispy French fries."
    res_new[2478]['query_processed'] = "During dinner, I treated myself to a delicious tangerine and a bottle of cool, unsweetened water."
    res_new[2488]['query_processed'] = "My lunch consisted of one Hot Pockets Beef & Cheddar turnover, alongside a 20 fl oz bottle of diet cola for a fizzy finish."
    res_new[2495]['query_processed'] = "For my midday meal, I opted for a refreshing cup of ready-to-drink protein shake and complemented it with a nutrition bar to keep me satisfied."
    res_new[2496]['query_processed'] = "I enjoyed a peanut butter sandwich cookie as a quick snack."
    res_new[2501]['query_processed'] = "To start my day, I indulged in a corn dog, enjoyed an orange, and treated myself to a cup of whole chocolate milk."
    res_new[2511]['query_processed'] = "This morning, I enjoyed a small brewed coffee with a splash of flavored liquid creamer, complemented by a meal replacement bar and a sprinkle of sugar from an individual packet."
    res_new[2515]['query_processed'] = "For my lunch, I savored a Hot Pocket, the perfect blend of chicken or turkey and cheese."
    res_new[2531]['query_processed'] = "This morning, I enjoyed a hearty chicken fillet biscuit sandwich and washed it down with a refreshing individual container of fruit juice blend."
    res_new[2539]['query_processed'] = "During lunch, I indulged in a piece of extra-large cheese pizza from a restaurant, followed by another piece of extra-large pizza with assorted meats other than pepperoni."
    res_new[2559]['query_processed'] = "For breakfast, I had a cup of reduced-fat (2%) milk, a cup of raw apple, an individual school container of apple juice, and a piece of medium crust cheese pizza from school lunch."
    res_new[2562]['query_processed'] = "For dinner, I had a fresh tangerine and a banana."
    res_new[2588]['query_processed'] = "At dinner tonight, I relished a classic Quarter Pounder with cheese, enjoyed some medium fast food french fries on the side, savored a medium cooked ground beef patty, and treated myself to a large frozen coffee drink with a delightful whipped cream topping."
    res_new[2605]['query_processed'] = "For my snack, I had a refreshing cup of tap water alongside a delicious vanilla light ice cream bar coated in chocolate."
    res_new[2607]['query_processed'] = "This afternoon, my snack consisted of a tube of low-fat fruit yogurt, a sweet orange, and a cup of crisp bottled water to wash it all down."
    res_new[2647]['query_processed'] = "I kicked off my breakfast with a bottle of unsweetened water and a delicious PowerBar to give me a boost."
    res_new[2686]['query_processed'] = "I kicked off my breakfast with a can of cola and indulged in a delightful yeast doughnut."
    res_new[2710]['query_processed'] = "For my snack, I had a delightful baby food cookie that was just the right size."
    res_new[2722]['query_processed'] = "While snacking, I enjoyed a perfectly ripe lychee, which added a tropical touch to my day."
    res_new[2724]['query_processed'] = "For lunch today, I had a satisfying whole wheat bagel with raisins alongside a bottle of iced black tea to quench my thirst."
    res_new[2729]['query_processed'] = "In my snack time, I savored a whole wheat English muffin, washed down with a 12 fl oz bottle of bottled water, and a sweet kiwi."
    res_new[2781]['query_processed'] = "For lunch, I had a Whopper from Burger King paired with a refreshing can of cola."
    res_new[2804]['query_processed'] = "At snack time, I had a medium chocolate chip cookie, a medium coconut cookie, a cup of fresh grapes, and a delicious clementine to round it all off."
    res_new[2807]['query_processed'] = "For lunch, I indulged in a Quarter Pounder with cheese and complemented it with a serving of fast food french fries from the dollar menu."
    res_new[2837]['query_processed'] = "For a satisfying brunch, I treated myself to a can of fruit-flavored soft drink paired with a classic Big Mac from McDonald's."
    res_new[2838]['query_processed'] = "During my snack time, I treated myself to a delicious ice cream bar in vanilla paired with a sweet and juicy tangerine."
    res_new[2845]['query_processed'] = "As a midday snack, I savored a regular taffy and a chocolate chip cookie, paired with a small cup of freshly brewed coffee and a dollop of butter from an individual container."
    res_new[2848]['query_processed'] = "During my afternoon snack, I enjoyed a delicious apple fritter with a generous tablespoon of butter."
    res_new[2861]['query_processed'] = "For a quick snack, I opted for a tasty breakfast tart and a crisp raw pear to keep things simple and satisfying."
    res_new[2862]['query_processed'] = "I started my day with a delicious breakfast that included one fried egg in oil, a refreshing cup of reduced-fat milk, and a fluffy egg white omelet cooked with a bit of oil."
    res_new[2863]['query_processed'] = "At dinner time, I treated myself to a refreshing bottle of unsweetened water, paired with a satisfying Quarter Pounder with cheese from McDonald's and a small order of their classic French fries."
    res_new[2925]['query_processed'] = "For breakfast, I opted for a sweet clementine and complemented it with a nutritious KIND bar."
    res_new[2935]['query_processed'] = "I started my day with a satisfying chicken fillet biscuit sandwich from a fast food restaurant and a convenient carton of orange juice."
    res_new[2959]['query_processed'] = "For my snack, I had a small single serving bag of cheese-flavored corn snacks, Cheetos, alongside a peanut butter and jelly sandwich on white bread."
    res_new[2963]['query_processed'] = "During my snack time, I enjoyed a juicy raw peach along with a sweet banana and a small bag of baked potato chips."
    res_new[2994]['query_processed'] = "During my snack time, I enjoyed a crunchy rod of hard pretzels and a juicy raw tangerine."
    res_new[3009]['query_processed'] = "I started my day with a breakfast tart and washed it down with a school-sized container of calcium-fortified orange juice."
    res_new[3010]['query_processed'] = "My lunch consisted of a 16.9 fl oz bottle of tap water, a single packet of ketchup, a small order of fast food french fries, and a tasty cheeseburger from Burger King."
    res_new[3024]['query_processed'] = "For dinner, I had a frosted cinnamon roll from Little Debbie along with a medium slice of white bread."
    res_new[3031]['query_processed'] = "At dinner, I enjoyed a 16.9 fl oz bottle of water alongside a delicious chocolate snack cake, a packet of mustard for flavor, a soft white hot dog bun, and a bun-size Italian sausage."
    res_new[3033]['query_processed'] = "At lunch, I indulged in a hearty Whopper cheeseburger, accompanied by a small single serving bag of plain potato chips for a satisfying crunch."
    res_new[3033]['query_processed'] = "At lunch, I indulged in a hearty Whopper with cheese, accompanied by a small single serving bag of plain potato chips for a satisfying crunch."
    res_new[3048]['query_processed'] = "During my lunch break, I enjoyed a medium cornbread muffin, along with a single serving bag of plain potato chips and a juicy raw orange."
    res_new[3049]['query_processed'] = "My afternoon snack consisted of a medium bag of Goldfish cheese crackers, complemented by a delicious freezer pop."
    res_new[3067]['query_processed'] = "I kicked off my day with a juicy raw peach paired with a refreshing bottle of bottled water."
    res_new[3091]['query_processed'] = "For dinner, I had a bun-sized Italian sausage served in a hot dog bun, topped with a tablespoon of barbecue sauce and a packet of mustard, washed down with a bottle of unsweetened bottled water."
    res_new[3102]['query_processed'] = "For a quick pick-me-up, I reached for a cup of plain Chex Mix, paired it with a small cookie, and finished it off with a sweet, crunchy pear."
    res_new[3110]['query_processed'] = "For a quick snack, I savored a breakfast tart, complemented by a cup of whole milk and a ready-to-eat chocolate pudding in a convenient snack-size container."
    res_new[3112]['query_processed'] = "For lunch, I had a regular bagel accompanied by a delicious egg omelet made with butter, and I rounded it off with a Quaker Chewy granola bar."
    res_new[3117]['query_processed'] = "For lunch, I savored a fried chicken thigh from the restaurant alongside a tender fried chicken breast, finishing it off with one delightful custard-filled doughnut and one yeast type doughnut."
    res_new[3140]['query_processed'] = "For my dinner, I indulged in a miniature of cheeseburger slider paired with an ice cream cookie sandwich."
    res_new[3143]['query_processed'] = "For a quick snack, I enjoyed a bottle of fruit-flavored soft drink and a deliciously soft salted pretzel, which was the perfect combination."
    res_new[3183]['query_processed'] = "For my lunch, I relished a small cheeseburger on a white bun, slathered with a packet of mustard and a tbsp ketchup, paired with a refreshing cup of low-fat milk and a small serving of plain potato chips."
    res_new[3192]['query_processed'] = "For breakfast today, I treated myself to a bottle of orange juice enriched with calcium, a satisfying chicken fillet sandwich from the cafeteria, and a lovely yeast doughnut on the side."
    res_new[3204]['query_processed'] = "For dinner tonight, I indulged in a piece of medium crust pizza loaded with pepperoni and also had a double cheeseburger from McDonald's to round out the meal."
    res_new[3205]['query_processed'] = res_new[3205]['query_pass_food_name_check']
    res_new[3218]['query_processed'] = "For dinner, I enjoyed a can of caffeine-free fruit-flavored soft drink alongside a delicious chicken thigh with the skin on. In addition, I had a chicken drumstick and a chicken breast."
    res_new[3222]['query_processed'] = "At dinner time, I enjoyed a juicy raw pear paired with a comforting biscuit topped with rich gravy."
    res_new[3245]['query_processed'] = "For my midday meal, I indulged in a Quarter Pounder with cheese and washed it down with a large serving of iced tea, sweetened to perfection."
    res_new[3249]['query_processed'] = "For breakfast today, I had a medium Danish pastry and a croissant sandwich filled with ham, egg, and cheese, making for a satisfying meal."
    res_new[3273]['query_processed'] = res_new[3273]['query_pass_food_name_check']
    res_new[3289]['query_processed'] = "For my midday meal, I savored a turkey or chicken burger on a wheat bun, paired with a tablespoon of ketchup and a packet of mustard, alongside a bottle of low-calorie sports drink."
    res_new[3295]['query_processed'] = "For lunch today, I had a hearty French bread cheese pizza, a small serving of whole grain cheese crackers, and a delightful cup of ready-to-drink fat-free chocolate milk."
    res_new[3298]['query_processed'] = "This morning, I enjoyed a warm chocolate croissant and a small flavored latte to start my day right."
    res_new[3305]['query_processed'] = "During my snack time, I enjoyed a delicious chunk of raw pineapple, a refreshing cube of watermelon, and a raw strawberry."
    res_new[3314]['query_processed'] = "For a quick lunch, I indulged in a kids meal with French fries and a juicy cheeseburger from Burger King."
    res_new[3329]['query_processed'] = "For lunch, I treated myself to a 16.9 fl oz bottle of tap water, an apple fritter, and a generous medium cup of vanilla ice cream."
    res_new[3364]['query_processed'] = "During snack time, I enjoyed a sweet cinnamon bun from Little Debbie, paired with a crunchy miniature dill pickle."
    res_new[3365]['query_processed'] = "I treated myself to a snack that included a bubbly 12 fl oz cola and a sweet guava fruit."
    res_new[3369]['query_processed'] = "For lunch, I indulged in a 12 fl oz can of diet cola, paired with a chicken drumstick complete with skin and a skinless chicken breast for a delightful balance."
    res_new[3372]['query_processed'] = "For my snack, I had a refreshing cup of tap water alongside a juicy mango."
    res_new[3398]['query_processed'] = "I had a satisfying lunch that included a tablespoon of butter next to a classic peanut butter and jelly sandwich, featuring regular peanut butter and jelly on wheat bread."
    res_new[3400]['query_processed'] = "I took a moment to savor a fresh, juicy pear and a delightful pouch of fruit snacks for my afternoon snack."
    res_new[3408]['query_processed'] = "This morning, my breakfast included a small bag of crispy pork skin rinds, paired with a refreshing 20 fl oz bottle of pepper soft drink, a fluffy meat-filled pastry, and a sweet doughnut topped with icing."
    res_new[3412]['query_processed'] = "For my snack, I sipped on a refreshing margarita and enjoyed a can of beer."
    res_new[3415]['query_processed'] = "This morning, I enjoyed a refreshing raw orange paired with a delicious cup of chocolate milk."
    res_new[3427]['query_processed'] = "During lunch, I treated myself to a sweet orange, a cup of NFS milk, and a hearty cheeseburger from the school cafeteria."
    res_new[3433]['query_processed'] = "I had a refreshing snack that included a ripe banana, a delicious Quaker Chewy 90 Calorie Granola Bar, a Clif Bar for extra energy, and a tablespoon of peanut butter to spread on the granola bar."
    res_new[3441]['query_processed'] = "For a quick snack, I relaxed with a delicious cocktail, savoring each sip."
    res_new[3454]['query_processed'] = "During my afternoon snack, I had two squares of graham crackers paired with a raw banana and a medium apple for some refreshing crunch."
    res_new[3462]['query_processed'] = "For breakfast, I started my day with a cup of reduced sugar chocolate milk and enjoyed it alongside a milk 'n cereal bar."
    res_new[3471]['query_processed'] = "For breakfast, I had a hash brown patty from a fast food place, drizzled with a packet of hot pepper sauce, alongside a McDonald's breakfast burrito filled with egg and meat, and I finished off the meal with a fresh banana."
    res_new[3483]['query_processed'] = "This morning, I savored a turkey burger on a white bun with an additional turkeyy patty drizzled with a tablespoon of creamy dressing, complemented by a refreshing 16 fl oz bottle of beer."
    res_new[3489]['query_processed'] = "This morning, I enjoyed a raw tangerine, accompanied by a strong espresso, and a delicious banana."
    res_new[3490]['query_processed'] = "For my snack, I had a raw banana and a fresh mango."
    res_new[3495]['query_processed'] = "At lunch, I kept hydrated with a 16.9 fl oz bottle of unsweetened water, complemented by a 32 fl oz can of Monster energy drink and a scrumptious doughnut covered in icing."
    res_new[3511]['query_processed'] = "For dinner, I had a brewed medium coffee with an ounce of half and half and a packet of sucralose to sweeten it up, along with a delicious cheeseburger from a fast food joint."
    res_new[3523]['query_processed'] = "For breakfast, I had a large caffeine-free fruit-flavored soft drink, which paired perfectly with my cheeseburger on a white bun, topped with a packet of mustard."
    res_new[3535]['query_processed'] = "In the morning, I had a slice of toasted wheat bread slathered with margarine from one individual container, a refreshing individual container of 100% grape juice, and a delightful powdered sugar doughnut to satisfy my sweet tooth."
    res_new[3545]['query_processed'] = "I decided to keep it simple for my snack, so I had one small raw apple and one raw pear."
    res_new[3557]['query_processed'] = "I treated myself to a clementine and a soft serve vanilla ice cream cone for a delightful afternoon snack."
    res_new[3565]['query_processed'] = "I started my day with a delicious egg omelet loaded with cheese and meat, accompanied by a small tortilla."
    res_new[3567]['query_processed'] = "At lunch today, I had a bottle of bottled water, a banana, and an orange, paired with a package of noodle soup and a one Hot Pockets Pepperoni Pizza turnover drizzled with tomato sauce."
    res_new[3577]['query_processed'] = "During my snack time, I enjoyed a slice of bologna paired with a sweet yeast doughnut and finished off with a medium-sized no-bake marshmallow cookie bar."
    res_new[3586]['query_processed'] = "For my dinner, I enjoyed a small soft white roll and a delicious breakfast tart, paired with a refreshing 12 fl oz can of cola, as well as a frankfurter on a bun, dressed with a packet mustard and a tablespoon of ketchup."
    res_new[3599]['query_processed'] = "I snacked on a delicious avocado paired with a zesty orange."
    res_new[3606]['query_processed'] = "This morning, I enjoyed a McDonald's sausage on a biscuit paired with a refreshing large pepper soft drink."
    res_new[3611]['query_processed'] = "At lunch, I indulged in a cup of reduced fat chocolate milk, a small serving of barbecue potato chips, and a savory chicken patty that was perfectly breaded."
    res_new[3614]['query_processed'] = "For dinner, I had a refreshing cup of unsweetened bottled water alongside a delicious vanilla ice cream sandwich."
    res_new[3619]['query_processed'] = "For breakfast, I had a delightful fruit waffle, slathered with a tablespoon of jelly, and washed it down with a small cup of brewed coffee with one fluid ounce liquid flavored creamer."
    res_new[3636]['query_processed'] = "My snack consisted of a vibrant peach paired with a colorful lollipop of hard candy for a fun twist."
    res_new[3645]['query_processed'] = "For my snack, I savored a regular microwave bag of butter-flavored popcorn, a rod of pretzels, a refreshing cup of bottled water, a bottle of liquid yogurt, a sweet piece of hard candy, a small single serving bag of plain corn chips, a raw orange, a raw banana, and a single serving bag of animal cookies."
    res_new[3688]['query_processed'] = "For dinner, I indulged in a Whopper with cheese from Burger King, paired with a small order of fast food french fries, a can of cola, and a medium cup of chocolate ice cream with additional ingredients."
    res_new[3697]['query_processed'] = "As a quick snack, I savored a delicious soft serve vanilla ice cream cone and a banana."
    res_new[3713]['query_processed'] = "For breakfast, I had a delicious croissant sandwich filled with bacon and egg, paired with a bottle of unsweetened water."
    res_new[3724]['query_processed'] = "During snack time, I indulged in a moon pie chocolate covered marshmallow pie and a cup of juicy raw grapes."
    res_new[3739]['query_processed'] = "This morning, my breakfast included a small cup of brewed coffee with a splash of sugar-free flavored creamer. I enjoyed it with a nutritious breakfast bar and a delicious sandwich made with egg, cheese, and sausage on an English muffin."
    res_new[3745]['query_processed'] = "For lunch, I had a peanut butter sandwich made with regular peanut butter on wheat bread, accompanied by a fresh tangerine."
    res_new[3762]['query_processed'] = "At brunch, I indulged in a small slice of white bread layered with deli ham, and I couldn't resist adding a sweet banana to my plate."
    res_new[3768]['query_processed'] = "To kick off my morning, I indulged in a Whopper with cheese, complemented by a 20 fl oz bottle of cola."
    res_new[3776]['query_processed'] = "For my breakfast, I had a refreshing cup of brewed coffee paired with a cup of egg white omelet, served in a medium whole wheat tortilla and finished off with a tablespoon of red salsa for an extra kick."
    res_new[3791]['query_processed'] = "During my afternoon snack, I enjoyed a refreshing cup of 2% milk paired with a delightful scooped vanilla ice cream cone and a juicy raw plum."
    res_new[3794]['query_processed'] = "This morning, I enjoyed a comforting cup of cooked instant oatmeal flavored with maple and topped it off with a tablespoon of creamy peanut butter."
    res_new[3799]['query_processed'] = "I kicked off my day with a hearty breakfast that included an egg and cheese sandwich on a biscuit, a cup of brewed coffee with 1 fl oz creamer, a ripe banana, a fresh peach, and a glass of refreshing tap water."
    res_new[3800]['query_processed'] = "I treated myself to a refreshing cup of gelatin dessert while munching on a delicious raw banana for my snack."
    res_new[3801]['query_processed'] = "During my snack time, I enjoyed a delicious slice of medium pepperoni pizza, accompanied by a light rice cake and a refreshing cup of unsweetened tap water."
    res_new[3815]['query_processed'] = "During my lunch break, I enjoyed a juicy orange and a small bag of flavored potato sticks for a nice crunch."
    res_new[3820]['query_processed'] = "This morning, I treated myself to a bottle of 100% orange juice and a sweet doughnut to kick off my breakfast."
    res_new[3831]['query_processed'] = "During my snack time, I enjoyed an ounce of reduced sugar oatmeal along with a tasty vanilla ice cream sandwich."
    res_new[3845]['query_processed'] = "For a quick snack, I savored a fresh tangerine and complemented it with a cup of rich vanilla ice cream."
    res_new[3879]['query_processed'] = "For breakfast, I had a delicious breakfast tart alongside a plain cake-type doughnut."
    res_new[3884]['query_processed'] = "During dinner, I relished a small patty hamburger on a fluffy white bun, drizzled with one tbsp ketchup, paired with an 8 fl oz bottle of 100% orange juice for a refreshing touch."
    res_new[3891]['query_processed'] = "During my snack time, I enjoyed a stick of chewing gum paired with a piece of part-skim mozzarella cheese."
    res_new[3919]['query_processed'] = "During my lunch break, I enjoyed a refreshing 20 fl oz bottle of unsweetened bottled water with a delicious medium hamburger and a tablespoon of barbecue sauce."
    res_new[3920]['query_processed'] = "As a mid-morning treat, I munched on a snack-sized tub of flavored potato chips alongside a chewy granola bar with yogurt coating from General Mills."
    res_new[3934]['query_processed'] = "For dinner, I enjoyed a satisfying cup of white rice, a generous cup of chicken chow mein with noodles, a sweet mango for a touch of dessert, and a glass of tap water to drink."
    res_new[3946]['query_processed'] = "For breakfast, I made an egg omelet packed with meat, accompanied by a tablespoon of ketchup for dipping."
    res_new[3966]['query_processed'] = "My breakfast typically includes a small serving of brewed coffee paired with a delicious Clif Bar."
    res_new[3982]['query_processed'] = "During my snack time, I enjoyed a juicy raw orange, a thin slice of Cuban bread, and a delightful clementine."
    res_new[4022]['query_processed'] = "For dinner, I prepared a medium flour tortilla and stuffed it with a bun-size savory pork sausage."
    res_new[4032]['query_processed'] = res_new[4032]['query_pass_food_name_check']
    res_new[4046]['query_processed'] = "This evening, my dinner featured a 12 fl oz can of beer, a delectable fruit-filled crepe, and a rich cheese-filled blintz."
    res_new[4140]['query_processed'] = "At snack time, I savored a cup of low-fat milk alongside a sweet, a juicy orange and an indulgent individual serving of vanilla ice cream."
    res_new[4163]['query_processed'] = "For lunch today, I relished a thick slice of deliciously cooked pork bacon, a fluffy egg omelet, a toasted English muffin with a tablespoon of jelly, and a slice of American cheese to round out the meal."
    res_new[4167]['query_processed'] = "For lunch today, I savored a bagel with a tablespoon of cream cheese, indulged in a chocolate doughnut, and sipped on a rich medium cappuccino."
    res_new[4192]['query_processed'] = "For dinner, I savored a Whopper with cheese from Burger King alongside a small order of french fries and a 12 fl oz can of a fruit-flavored soft drink."
    res_new[4200]['query_processed'] = "I treated myself to lunch with a medium roll, a cup of fried diced beef steak, a crisp pear, and a smooth cup of low-fat chocolate milk."
    res_new[4219]['query_processed'] = "My snack consisted of a vibrant Orange Blossom drink and a tasty Reese's Peanut Butter Cup served in 0.6 oz."
    res_new[4222]['query_processed'] = "For my snack, I had a delicious fruit, a chocolate-coated vanilla ice cream bar, and a small box of raisins."
    res_new[4240]['query_processed'] = "For my dinner, I prepared a medium roasted chicken breast, paired with a medium delicious baked potato, peel included, and I sipped on a chilled bottle of unsweetened water."
    res_new[4243]['query_processed'] = "For my dinner, I enjoyed a perfectly sautéed chicken wing alongside a hearty fried chicken breast with its crunchy coating, just like the ones from the local eatery."
    res_new[4255]['query_processed'] = "For a light snack, I savored a sweet, fresh peach alongside a crisp pear."
    res_new[4257]['query_processed'] = "During my snack time, I had a cup of cheese Goldfish crackers alongside a delicious nutrition bar from Zone Perfect Classic Crunch, washed down with a refreshing 12 fl oz can of diet cola."
    res_new[4269]['query_processed'] = "For my breakfast, I made a simple yet delicious scrambled egg without added fat, which I paired with a cup of reduced-fat (2%) milk."
    res_new[4276]['query_processed'] = "For lunch, I had a delicious steak and cheese submarine sandwich topped with fresh lettuce and tomato, accompanied by a bottle of 100% apple juice and a crisp raw pear."
    res_new[4290]['query_processed'] = "For lunch, I decided to have a raw orange, a crisp pear, and a fizzy cola from a 12 fl oz can."
    res_new[4294]['query_processed'] = "For my snack, I enjoyed a regular oatmeal cupcake alongside a Quaker Chewy granola bar."
    res_new[4303]['query_processed'] = "For my snack, I enjoyed a small brewed iced coffee alongside a McDonald's cheeseburger topped with a tablespoon of ketchup."
    res_new[4314]['query_processed'] = "This morning, I enjoyed a delicious Jimmy Dean sandwich including egg, cheese, and sausage biscuit, complemented by a ripe banana and a refreshing bottle of tap water."
    res_new[4321]['query_processed'] = "During lunch, I savored a delicious Italian sausage in a hot dog bun, paired with a small bag of lightly salted potato chips and a chilled bottle of unsweetened water."
    res_new[4326]['query_processed'] = "I enjoyed a delightful breakfast consisting of a cup of General Mills Cocoa Puffs, a rich cup of whole chocolate milk, a sweet breakfast tart, and a refreshing individual carton of 100% orange juice."
    res_new[4355]['query_processed'] = "During my lunch break, I enjoyed a fresh banana alongside a cup of refreshing tap water and a delicious breakfast tart."
    res_new[4373]['query_processed'] = "This afternoon, my snack consisted of a single raw nectarine complemented by a tasty banana."
    res_new[4407]['query_processed'] = "For breakfast, I savored a whole egg fried in oil, alongside a regular whole wheat bagel topped with a slice of luncheon meat, complemented by a warm cup of decaffeinated coffee with one fluid ounce of cream."
    res_new[4430]['query_processed'] = "For my morning meal, I had a regular slice of whole wheat toast, a juicy banana, and a can of carbonated water to quench my thirst."
    res_new[4445]['query_processed'] = "To kick off my morning, I had a delightful breakfast tart alongside a refreshing serving of 100% orange juice with calcium in an individual school container."
    res_new[4447]['query_processed'] = "I kicked off my morning with a small warm cup of brewed decaffeinated coffee and a nutritious breakfast bar."
    res_new[4450]['query_processed'] = "For a quick snack, I opted for a small cookie, a pear, and a satisfying cup of plain Chex Mix."
    res_new[4456]['query_processed'] = "To start my day, I enjoyed a small cup of freshly brewed coffee with 1 fl oz flavored creamer, alongside a fruit waffle and a tablespoon of jelly to spread over it."
    res_new[4473]['query_processed'] = "For my breakfast, I savored a turkey burger on a soft white bun, paired with a patty of ground turkey, drizzled with 1 tablespoon creamy dressing, and washed it down with a 16 fl oz bottle of beer."
    res_new[4480]['query_processed'] = "During brunch, I delighted in a Big Mac from McDonald's along with a can of fruit-flavored soft drink to quench my thirst."
    res_new[4481]['query_processed'] = "I enjoyed a refreshing snack consisting of a creamy vanilla ice cream bar and a sweet tangerine."
    res_new[4490]['query_processed'] = "I started my day with a 5.3 oz serving of Greek yogurt, which is made from nonfat milk and fruit, along with a banana."
    res_new[4492]['query_processed'] = "At lunch, I relished a Hot Pockets Pepperoni Pizza turnover, paired with a small package of noodle soup, a raw orange, a banana, and a chilled bottle of unsweetened water to wash it all down."
    res_new[4493]['query_processed'] = "I began my day with a cup of bottled water and a hearty chicken fillet biscuit, perfect for breakfast on the go."
    res_new[4496]['query_processed'] = "During my snack time, I enjoyed a juicy orange alongside a tablespoon of delicious chocolate hazelnut spread."
    res_new[4512]['query_processed'] = "For breakfast, I had a delicious croissant sandwich filled with ham, egg, and cheese, paired with a medium plain Danish pastry."
    res_new[4515]['query_processed'] = "I sipped on a small brewed coffee with 1 fl oz whole milk for my snack today."
    res_new[4545]['query_processed'] = "-1"
    res_new[4587]['query_processed'] = "This morning, I enjoyed an egg omelet made with oil, along with a delicious cheese quesadilla and a medium soft taco filled with savory meat."
    res_new[4596]['query_processed'] = "At lunchtime, I indulged in a delicious sweet cinnamon roll from Little Debbie, paired with a king-size pack of Reese's Peanut Butter Cups and a medium serving of reduced-fat cheese corn snacks."
    res_new[4603]['query_processed'] = "For my midday meal, I had a satisfying Quarter Pounder with cheese from McDonald's, complemented by a large order of crispy French fries, a dipping-size honey mustard dressing, and a large caffeine-free fruit-flavored soft drink."
    res_new[4611]['query_processed'] = "This morning, my breakfast featured a slice of school lunch cheese pizza, paired with a school container of fresh apple juice, a cup of raw apple, and a refreshing cup of 2% reduced fat milk."
    res_new[4615]['query_processed'] = "For my snack, I had a can of cola and a fresh orange."
    res_new[4616]['query_processed'] = "During lunch, I savored a delicious kolache stuffed with meat, a slice of cheddar cheese on the side, and a light, airy doughnut to round off the meal."
    res_new[4617]['query_processed'] = "I treated myself to a satisfying lunch that included a Quarter Pounder with cheese, a large fast-food French fries, and a large pepper-flavored soft drink."
    res_new[4632]['query_processed'] = "At snack time, I munched on a piece of fruit leather, enjoyed a refreshing peach, and indulged in a fudgesicle."
    res_new[4652]['query_processed'] = "While snacking, I enjoyed a small bag of flavored potato chips and complemented it with a fresh pear, making for a delightful combination."
    res_new[4654]['query_processed'] = "For breakfast, I enjoyed a piece of pizza featuring meat toppings other than pepperoni straight from the school lunch menu, and I rounded it off with a sweet, succulent orange."
    res_new[4655]['query_processed'] = "At lunchtime, I savored a cheeseburger from the school cafeteria, washed down with a cup of milk and complemented by a raw orange."
    res_new[4661]['query_processed'] = "For breakfast, I savored a mini baguette, enhanced with a tablespoon of soy sauce, complemented by a fried egg and a cooked egg yolk."
    res_new[4670]['query_processed'] = "At snack time, I savored a small brewed coffee with one fluid ounce of half and half and a teaspoon of sucralose for a delightful touch of sweetness."
    res_new[4682]['query_processed'] = "For lunch today, I had a sandwich filled with roast beef and cheese, drizzled with one tablespoon of horseradish sauce, along with a cup of crispy French fries on the side."
    res_new[4709]['query_processed'] = "I munched on a pouch of fruit leather and paired it with a sweet, fresh pear during my snack break."
    res_new[4710]['query_processed'] = "For breakfast today, I indulged in a delicious whole wheat bagel with 1 tbsp cream cheese and 1 tbsp jam, complemented by a refreshing individual carton of 100% orange juice."
    res_new[4742]['query_processed'] = "During my lunch break, I enjoyed a tasty bagel alongside a buttery egg omelet and a Quaker Chewy granola bar for some extra crunch."
    res_new[4753]['query_processed'] = "During my snack time, I indulged in a fig bar cookie, spread a tablespoon of creamy peanut butter on it, and treated myself to an oreo thin chocolate sandwich."
    res_new[4789]['query_processed'] = "For my lunch, I savored a juicy pork sausage served in a classic hot dog bun, slathered with a packet of mustard."
    res_new[4804]['query_processed'] = "I enjoyed a delicious snack of one juicy raw orange paired with a smooth raw avocado."
    res_new[4810]['query_processed'] = "Today’s lunch consisted of a turkey burger on a wheat bun, with a packet of mustard and a tablespoon of ketchup, and a crisp bottle of low-calorie sports drink to keep me refreshed."
    res_new[4843]['query_processed'] = "For dinner, I savored a classic Quarter Pounder with cheese, complemented by a medium serving of golden french fries and a bubbly medium cola to drink."
    res_new[4855]['query_processed'] = "For dinner, I had a delicious biscuit smothered in creamy gravy alongside a fresh, raw pear."
    res_new[4866]['query_processed'] = "I started my day with a nourishing breakfast that featured a boiled egg, a snack-size slice of whole wheat bread filled with raisins, a cooked egg yolk, 1 fl oz hot herbal tea, and 1 fl oz of whole milk."
    res_new[4878]['query_processed'] = "My dinner consisted of a cup of lean beef steak that was broiled to juicy perfection, complemented by a cup of deliciously cooked broccoli."
    res_new[4879]['query_processed'] = "For my afternoon snack, I chose a refreshing bottle of water, a classic 12 fl oz cola, and a fun freezer pop to keep things cool."
    res_new[4889]['query_processed'] = "I treated myself to lunch with a bun-size Italian sausage tucked into a hot dog bun, a sweet chocolate snack cake with icing, and a chilled bottle of unsweetened water to drink."
    res_new[4890]['query_processed'] = "For dinner, I enjoyed a bun-sized Italian sausage nestled in a white hot dog bun, drizzled with one packet of mustard, and finished off with a delicious chocolate snack cake and a refreshing bottle of water."
    res_new[4894]['query_processed'] = "-1"
    res_new[4898]['query_processed'] = "During snack time, I enjoyed a cup of Italian ice paired with a delicious fruit."
    res_new[4908]['query_processed'] = "During my snack time, I savored a cup of freshly brewed coffee with one fluid ounce of coffee creamer, complemented by a refreshing cup of XS energy drink."
    res_new[4911]['query_processed'] = "At lunchtime, I treated myself to a meat- and cheese-filled Hot Pocket, the Beef & Cheddar kind, with a slice of rich Colby Jack cheese on the side."
    res_new[4916]['query_processed'] = "During my afternoon snack, I treated myself to a small rich chocolate milkshake from the local fast food joint, complemented by a juicy raw plum."
    res_new[4928]['query_processed'] = "My afternoon snack consisted of a small serving of Goldfish cheese crackers and a meal replacement bar to keep me satisfied."
    res_new[4940]['query_processed'] = "During lunch, I relished a sandwich filled with regular peanut butter on whole wheat bread, a small single-serving bag of potato chips, and a refreshing raw peach."
    res_new[4949]['query_processed'] = "My snack consisted of a decadent nut roll with caramel, a small bag of sour cream and onion potato chips, and a McDonald's hamburger with a side of crispy French fries."
    res_new[4955]['query_processed'] = "For my snack, I enjoyed a delicious banana, accompanied by a regular microwave bag of butter-flavored popcorn, a rod of hard pretzels, a small single serving bag of plain corn chips, a single serving bag of animal cookies, and a refreshing bottle of unsweetened water. To round out the experience, I also treated myself to a piece of fruit, a juicy orange, and a bottle of liquid yogurt, along with a cup of hard candy for a sweet finish."
    res_new[4997]['query_processed'] = "During dinner, I had a satisfying McDouble cheeseburger and washed it down with a 20 fl oz bottle of unsweetened water."
    res_new[4999]['query_processed'] = "For my lunch, I savored a piece of pepperoni pizza with a delightful stuffed crust, along with a refreshing cup of reduced sugar chocolate milk. To add some freshness, I included a small raw apple and an orange."
    res_new[5007]['query_processed'] = "For breakfast today, I had a juicy clementine, a medium slice of whole wheat bread, a slice of cheddar cheese, and a tube of yogurt made with low-fat milk and fruit."
    res_new[5014]['query_processed'] = "At lunchtime, I enjoyed a satisfying medium cup of vanilla ice cream alongside a warm apple fritter, complemented by a refreshing bottle of tap water."
    res_new[5016]['query_processed'] = "I decided to have a snack consisting of a peach and a delightful vanilla ice cream sandwich."
    res_new[5028]['query_processed'] = "During my lunch break, I treated myself to a delicious Big Mac from McDonald's, paired with a refreshing medium cola and a side of crispy medium french fries."
    res_new[5036]['query_processed'] = "To start my day, I savored a cup of NFS chocolate milk and enjoyed a raw orange for a burst of flavor."
    res_new[5108]['query_processed'] = "For lunch, I had a delicious croissant sandwich filled with sausage and egg, accompanied by a refreshing can of cola."
    res_new[5175]['query_processed'] = "For a quick snack, I grabbed a Quaker Chewy Granola Bar, an animal cookie bag, a peanut butter and jelly sandwich, and a cup of bottled water to keep me hydrated."
    res_new[5191]['query_processed'] = "At dinner, I had a delicious piece of extra-large cheese pizza and a piece of extra-large pepperoni pizza from a fast food joint, complemented by a 20 fl oz bottle of Gatorade G for a burst of energy."
    res_new[5195]['query_processed'] = "For brunch, I savored a French bread pizza topped with pepperoni, a crunchy rice cake, and washed it all down with a cup of sweetened bottled water."
    res_new[5211]['query_processed'] = "For lunch today, I had a medium cut of lean cooked spareribs, a tasty cocktail of Polish sausage, and a 12 fl oz can of my favorite pepper soft drink."
    res_new[5221]['query_processed'] = "-1"
    res_new[5254]['query_processed'] = "I savored a Frankfurter beef hot dog sandwich on a white bun for dinner, along with a small salted soft pretzel on the side."
    res_new[5261]['query_processed'] = "During my afternoon snack, I indulged in a piece of hard candy while savoring a delicious Hot Pockets filled with pepperoni and cheese."
    res_new[5300]['query_processed'] = "For my lunch, I had a small bag of nacho cheese Doritos, and a cup of refreshing bottled water to wash it all down. To make it even better, I also enjoyed a pack of two General Mills Nature Valley Crunchy Granola Bars and a delicious peanut butter and jelly sandwich, all with a pouch of juice from Kool-Aid Jammers."
    res_new[5409]['query_processed'] = "I enjoyed a delightful snack that included one medium chocolate chip cookie paired with a small brownie cookie, just the right amount of sweetness."
    res_new[5437]['query_processed'] = "For breakfast, I had a delicious breakfast tart paired with a refreshing Capri Sun fruit juice drink."
    res_new[5470]['query_processed'] = "For a refreshing snack, I opted for a 20 fl oz bottle of caffeine-free fruit-flavored soft drink paired with a zesty margarita."
    res_new[5485]['query_processed'] = "For a quick snack, I opted for a 6 oz container of low-fat Greek yogurt mixed with fruit, along with a tasty granola bar from Quaker."
    res_new[5543]['query_processed'] = "I had a refreshing snack of a raw baby carrot together with a low-fat cereal crust breakfast bar filled with fruit."
    res_new[5544]['query_processed'] = "During snack time, I enjoyed a peanut butter sandwich cookie with a refreshing 1 fl oz serving of reduced-fat (2%) milk."
    res_new[5545]['query_processed'] = "At dinner, I indulged in a delicious cheese pizza from frozen, served alongside a chilled can of fruit-flavored soft drink."
    res_new[5557]['query_processed'] = "This morning, I enjoyed a cup of Honey Nut Cheerios, soaking in the sweetness of honey, complemented by a refreshing cup of whole milk."
    res_new[5559]['query_processed'] = "For breakfast today, I had a small brewed coffee, which I lightened with 1 fl oz of flavored coffee creamer, paired with a soft-boiled egg."
    res_new[5635]['query_processed'] = "For my snack, I had a peanut butter sandwich cookie along with a jar of Beech-Nut Stage 1 applesauce."
    res_new[5717]['query_processed'] = "At dinner, I enjoyed a crispy fried chicken thigh along with a succulent fried chicken breast, all complemented by a refreshing bottle of bottled water."
    res_new[5736]['query_processed'] = "For dinner, I enjoyed a cup of cooked, diced beef short ribs, accompanied by a cup of grilled chicken thighs with sauce, a bun-size Polish sausage and a frankfurter."
    res_new[5761]['query_processed'] = "This morning's breakfast featured a tasty package of breakfast tarts, a bottle of unsweetened water, and a satisfying Clif Bar."
    res_new[5792]['query_processed'] = "For breakfast, I started my day with a delicious breakfast tart and a cup of chocolate milk made from syrup with reduced fat milk."
    res_new[5818]['query_processed'] = "For breakfast, I had a Toaster Strudel filled with fruit alongside a plain frozen waffle."
    res_new[5836]['query_processed'] = "For my dinner, I enjoyed a Hot Pockets Four Cheese Pizza turnover with tomato-based sauce, alongside a refreshing cup of sweetened almond milk."
    res_new[5837]['query_processed'] = "My snack consisted of a delightful slice of sweet roll without frosting paired with a cup of creamy sweetened almond milk."
    res_new[5868]['query_processed'] = "I enjoyed a small quesadilla with egg for breakfast, complemented by 1 fl oz drink of tap water."
    res_new[5962]['query_processed'] = "This snack time, I indulged in a piece of toffee and relished a cup of yellow cake with its sweet icing, accompanied by 1 fl oz of tap water."
    res_new[5967]['query_processed'] = "For breakfast, I treated myself to a medium frosted cinnamon bun alongside a Hot Pocket turnover filled with egg, meat, and cheese."
    res_new[6020]['query_processed'] = "I enjoyed a satisfying dinner featuring a fried chicken drumstick, skin and all, accompanied by a hearty fried chicken thigh, both from a popular fast food spot."
    res_new[6037]['query_processed'] = "For a sweet afternoon snack, I had a gummy bear and a Keebler Rainbow Chips Deluxe cookie to satisfy my cravings."
    res_new[6155]['query_processed'] = "-1"
    res_new[6182]['query_processed'] = "I had a satisfying dinner featuring a fried chicken drumstick and a chicken breast, both perfectly coated and crispy, alongside a large cola and a cup of fast food fries."
    res_new[6188]['query_processed'] = "I started my day with a breakfast tart and washed it down with a carton of 100% orange juice."
    res_new[6252]['query_processed'] = "This morning, I enjoyed a delicious breakfast tart along with an individual school container of grape juice and a refreshing cup of 2% milk."
    res_new[6283]['query_processed'] = "At lunch today, I indulged in a cup of a wholesome fruit smoothie made with whole fruits and dairy, and I added a fresh raw peach for a tasty touch."
    res_new[6288]['query_processed'] = "For my snack, I sipped on a 12 fl oz can of caffeine-free fruit-flavored soft drink, savored an individual school container of 100% apple juice, and enjoyed a bottle of unsweetened bottled water, all while refreshing myself with 1 fl oz of tap water."
    res_new[6298]['query_processed'] = "For lunch, I had a can of decaffeinated cola alongside a Taco Bell Crunchwrap Supreme filled with meat and sour cream."
    res_new[6314]['query_processed'] = "For breakfast, I treated myself to a can of cola and a Hot Pocket turnover stuffed with chicken and cheese."
    res_new[6318]['query_processed'] = "During my mid-afternoon break, I enjoyed a delicious mojito paired with a container of 100% grape juice."
    res_new[6338]['query_processed'] = "For breakfast, I relished a croissant sandwich that was stuffed with sausage, egg, and cheese, washed down with a large iced coffee."
    res_new[6359]['query_processed'] = "I enjoyed a hearty lunch today with a serving of nachos smothered in cheese and a drink of chilled bottle of unsweetened water to wash it down."
    res_new[6363]['query_processed'] = "I treated myself to a peach and washed it down with a cup of bottled unsweetened water for my snack."
    res_new[6374]['query_processed'] = "For breakfast, I savored a cup of rich hot chocolate and indulged in a chocolate sandwich cookie, creating the perfect morning combination."
    res_new[6382]['query_processed'] = "For my snack, I indulged in a small chocolate chip cookie alongside a fresh, juicy peach."
    res_new[6397]['query_processed'] = "For breakfast, I indulged in a Toaster Strudel Danish pastry filled with fruit, accompanied by a refreshing cup of tap water."
    res_new[6415]['query_processed'] = "I enjoyed a delightful moon pie with a refreshing cup of sweetened almond milk for my snack."
    res_new[6488]['query_processed'] = "For a quick snack, I grabbed a stick of mozzarella cheese, indulged in a Pepperoni Pizza Hot Pocket turnover with its delightful meat and cheese filling and tomato sauce, and sipped on a cup of tap water."
    res_new[6542]['query_processed'] = "My snack consisted of a regular slice of whole wheat bread and a tasty gummy bear to satisfy my sweet tooth."
    res_new[6551]['query_processed'] = "At dinner time, I dug into a large burrito filled with savory meat, enhanced by the freshness of a raw cilantro scattered on top."
    res_new[6555]['query_processed'] = "For a quick snack, I grabbed a stick of mozzarella cheese and complemented it with a stick of sugar-free chewing gum."
    res_new[6602]['query_processed'] = "For a delightful snack, I opted for a chilled martini that added a touch of elegance to my day."
    res_new[6649]['query_processed'] = "For dinner, I had a Taco Bell Crunchwrap Supreme burrito filled with meat and sour cream, paired with a 12 fl oz can of diet cola."
    res_new[6651]['query_processed'] = "I wrapped up my day with a satisfying dinner that included a Hot Pockets Pepperoni Pizza turnover loaded with meat and cheese, and a large drink of diet iced tea to cool off."
    res_new[6656]['query_processed'] = "For dinner, I relished a stick of fish, paired with a 1 fl oz nutritious fruit juice drink full of vitamin C and a bottle of refreshing water."
    res_new[6676]['query_processed'] = "I treated myself to a drink of frozen margarita during lunch, along with a cup of bottled fruit smoothie for a sweet touch."
    res_new[6737]['query_processed'] = "For my dinner, I savored a delicious Crunchwrap Supreme burrito with meat and sour cream, paired with a cup of tap water to wash it down."
    res_new[6762]['query_processed'] = "For a satisfying snack, I had a delicious breakfast tart alongside a fun-sized SNICKERS Bar."
    res_new[6800]['query_processed'] = "For a quick snack, I munched on a cup of animal cookies alongside a whole peach."
    res_new[6809]['query_processed'] = "For my snack, I had a piece of plain milk chocolate candy, a nutrition bar, a medium slice of wheat bread, and a stick of part-skim mozzarella cheese."
    res_new[6820]['query_processed'] = "During lunch, I had a convenient jar of junior vegetable and chicken baby food and a delicious serving of Gerber's strained applesauce."
    res_new[6862]['query_processed'] = "For a quick snack, I had a gummy fish and a Kit Kat in the fun-size portion."
    res_new[6875]['query_processed'] = "For a quick snack, I munched on a fun-size pack of M&M's Peanut Chocolate Candies and savored a Hot Pocket turnover filled with beef and cheddar cheese."
    res_new[6889]['query_processed'] = "-1"
    res_new[6917]['query_processed'] = "For a quick snack, I savored a breakfast tart paired with a lovely medium chocolate chip cookie."
    res_new[6937]['query_processed'] = "My brunch consisted of a serving of strained baby food bananas from Gerber and a delightful tablespoon of strained pears."
    res_new[6952]['query_processed'] = "I decided to have a quick snack, which included a pack of hard candy, a stick of part-skim mozzarella cheese, and a delicious piece of chewing gum."
    res_new[7060]['query_processed'] = res_new[7060]['query_pass_food_name_check']
    res_new[7065]['query_processed'] = res_new[7065]['query_pass_food_name_check']
    res_new[7068]['query_processed'] = res_new[7068]['query_pass_food_name_check']
    res_new[7070]['query_processed'] = "For my dinner, I enjoyed a comforting bowl of noodle soup and a delicious Hot Pockets Philly Steak and Cheese turnover with no gravy."
    res_new[7071]['query_processed'] = res_new[7071]['query_pass_food_name_check']
    res_new[7081]['query_processed'] = res_new[7081]['query_pass_food_name_check']
    res_new[7083]['query_processed'] = res_new[7083]['query_pass_food_name_check']
    res_new[7088]['query_processed'] = res_new[7088]['query_pass_food_name_check']
    res_new[7095]['query_processed'] = res_new[7095]['query_pass_food_name_check']




    fail_count_after_remove_special_cases = 0
    for idx, r in tqdm(enumerate(res_new)):
        if r['query_processed'] == "":
            # remove fruit, tart
            description = ast.literal_eval(r['description'])
            unit = ast.literal_eval(r['unit'])
            unit_in_query = r['unit_in_query']
            query = r['query_pass_food_name_check']
            assert len(description) == len(unit) == len(unit_in_query)

            unit_in_query_new = []
            for i in range(len(description)):
                if unit_in_query[i] == '-1':
                    if description[i] == 'Breakfast tart' and unit[i] == '1 Pop Tart':
                        if "a tasty breakfast tart" in query.lower():
                            unit_in_query_new.append("a tasty breakfast tart")
                        elif "a delightful Pop Tart" in query:
                            unit_in_query_new.append("a delightful Pop Tart")
                        else:
                            print('a')
                    elif description[i] == 'Breakfast tart, lowfat' and unit[i] == '1 Pop Tart':
                        if "a low-fat breakfast tart" in query.lower():
                            unit_in_query_new.append("a low-fat breakfast tart")
                        else:
                            print('a')
                    elif description[i] == 'Peach, raw' and unit[i] == '1 fruit':
                        if "a refreshing peach" in query.lower():
                            unit_in_query_new.append("a refreshing peach")
                        elif "a lovely fresh peach" in query.lower():
                            unit_in_query_new.append("a lovely fresh peach")
                        elif "a fresh peach" in query.lower():
                            unit_in_query_new.append("a fresh peach")
                        elif "a juicy peach" in query.lower():
                            unit_in_query_new.append("a juicy peach")
                        else:
                            print('a')
                    elif description[i] == 'Banana, raw' and unit[i] in ['1 fruit', "1 banana"]:
                        if "a delicious banana" in query.lower():
                            unit_in_query_new.append("a delicious banana")
                        elif "a fresh banana" in query.lower():
                            unit_in_query_new.append("a fresh banana")
                        elif "a banana" in query.lower():
                            unit_in_query_new.append("a banana")
                        else:
                            print('a')
                    elif description[i] == 'Orange, raw' and unit[i] in ['1 fruit', "1 orange"]:
                        if "a juicy raw orange" in query.lower():
                            unit_in_query_new.append("a juicy raw orange")
                        elif 'a delicious orange' in query.lower():
                            unit_in_query_new.append('a delicious orange')
                        elif "a refreshing orange" in query.lower():
                            unit_in_query_new.append("a refreshing orange")
                        else:
                            print('a')
                    elif description[i] == 'Gordita/sope shell, plain, no filling' and unit[i] in ['1 shell (3 - 4" dia)']:
                        if "a soft gordita shell" in query.lower():
                            unit_in_query_new.append("a soft gordita shell")
                        else:
                            print('a')
                    elif description[i] == 'Roll, sweet, cinnamon bun, frosted' and unit[i] in ['1 Little Debbie']:
                        if "a sweet cinnamon roll" in query.lower():
                            unit_in_query_new.append("a sweet cinnamon roll")
                        else:
                            print('a')
                    elif description[i] == 'Sausage on biscuit' and unit[i] in ["1 McDonald's regular"]:
                        if "a warm sausage on a biscuit from mcdonald's" in query.lower():
                            unit_in_query_new.append("a warm sausage on a biscuit from McDonald's")
                        else:
                            print('a')
                    elif description[i] == 'Nectarine, raw' and unit[i] in ['1 fruit']:
                        if "a raw nectarine" in query.lower():
                            unit_in_query_new.append("a raw nectarine")
                        else:
                            print('a')
                    elif description[i] == 'Nutrition bar (Clif Kids Organic Zbar)' and unit[i] in ['1 bar']:
                        if "a tasty nutrition bar" in query.lower():
                            unit_in_query_new.append("a tasty nutrition bar")
                        else:
                            print('a')  
                    elif description[i] == 'Coffee creamer, liquid, sugar free, flavored' and unit[i] in ['1 individual container']:
                        if "a splash of sugar-free flavored creamer" in query.lower():
                            unit_in_query_new.append("a splash of sugar-free flavored creamer")
                        else:
                            print('a')        
                    elif description[i] == 'Frankfurter or hot dog, beef' and unit[i] in ['1 frankfurter']:
                        if "a flavorful beef frankfurter" in query.lower():
                            unit_in_query_new.append("a flavorful beef frankfurter")
                        else:
                            print('a')      
                    elif description[i] == 'Pear, raw' and unit[i] in ['1 fruit']:
                        if "a delicious raw pear" in query.lower():
                            unit_in_query_new.append("a delicious raw pear")
                        elif "a succulent raw pear" in query.lower():
                            unit_in_query_new.append("a succulent raw pear")
                        else:
                            print('a')   
                    elif description[i] == 'Egg omelet or scrambled egg, made with butter' and unit[i] in ['1 egg']:
                        if "a fluffy omelet" in query.lower():
                            unit_in_query_new.append("a fluffy omelet")
                        elif "a delicious egg omelet" in query.lower():
                            unit_in_query_new.append("a delicious egg omelet")
                        else:
                            print('a')   
                    elif description[i] == 'Cereal or granola bar (Quaker Chewy Dipps Granola Bar)' and unit[i] in ['1 bar']:
                        if "a Quaker Chewy Dipps granola bar" in query:
                            unit_in_query_new.append("a Quaker Chewy Dipps granola bar")
                        else:
                            print('a')  
                    elif description[i] == 'Nachos with meat, cheese, and sour cream' and unit[i] in ['1 Nachos Supreme']:
                        if "a Nachos Supreme" in query:
                            unit_in_query_new.append("a Nachos Supreme")
                        else:
                            print('a')   
                    elif description[i] == 'Popsicle' and unit[i] in ['1 single stick']:
                        if "a popsicle" in query.lower():
                            unit_in_query_new.append("a popsicle")
                        else:
                            print('a')  
                    elif description[i] == 'Ice cream cone, scooped, vanilla, waffle cone' and unit[i] in ['1 cone']:
                        if "a classic waffle cone" in query.lower():
                            unit_in_query_new.append("a classic waffle cone")
                        else:
                            print('a')  
                    elif description[i] == 'Ice cream cone, scooped, vanilla' and unit[i] in ['1 cone']:
                        if "a classic cone" in query.lower():
                            unit_in_query_new.append("a classic cone")
                        else:
                            print('a')  
                    elif description[i] == 'Hamburger (McDonalds)' and unit[i] in ['1 hamburger']:
                        if "a delicious McDonald's hamburger" in query:
                            unit_in_query_new.append("a delicious McDonald's hamburger")
                        elif "a delicious hamburger" in query:
                            unit_in_query_new.append("a delicious hamburger")
                        else:
                            print('a')  
                    elif description[i] == 'Avocado, raw' and unit[i] in ['1 fruit']:
                        if "a fresh avocado" in query:
                            unit_in_query_new.append("a fresh avocado")
                        else:
                            print('a')  
                    elif description[i] == 'Clementine, raw' and unit[i] in ['1 fruit']:
                        if "a fresh clementine" in query:
                            unit_in_query_new.append("a fresh clementine")
                        else:
                            print('a') 
                    elif description[i] == 'Plum, raw' and unit[i] in ['1 fruit']:
                        if "a raw plum" in query:
                            unit_in_query_new.append("a raw plum")
                        elif "a juicy medium plum" in query:
                            unit_in_query_new.append("a juicy medium plum")
                        else:
                            print('a') 
                    elif description[i] == 'Doughnut, chocolate' and unit[i] in ['1 doughnut']:
                        if "a delicious chocolate doughnut" in query:
                            unit_in_query_new.append("a delicious chocolate doughnut")
                        else:
                            print('a') 
                    elif description[i] == 'Nutrition bar (Clif Bar)' and unit[i] in ['1 bar']:
                        if "a Clif nutrition bar" in query:
                            unit_in_query_new.append("a Clif nutrition bar")
                        else:
                            print('a') 
                    elif description[i] == 'Tangerine, raw' and unit[i] in ['1 fruit']:
                        if "a juicy tangerine" in query:
                            unit_in_query_new.append("a juicy tangerine")
                        else:
                            print('a') 
                    elif description[i] == 'Butter, stick' and unit[i] in ['1 tablespoon']:
                        if "a tablespoon of butter" in query:
                            unit_in_query_new.append("a tablespoon of butter")
                        else:
                            print('a') 
                    elif description[i] == 'Empanada, Mexican turnover, filled with cheese and vegetables' and unit[i] in ['1 empanada']:
                        if "a flavorful Mexican empanada" in query:
                            unit_in_query_new.append("a flavorful Mexican empanada")
                        else:
                            print('a') 
                    elif description[i] == 'Potato, french fries, fast food' and unit[i] in ['1 small fast food order']:
                        if "a small serving of French fries" in query:
                            unit_in_query_new.append("a small serving of French fries")
                        else:
                            print('a') 
                    elif description[i] == 'Whopper with cheese (Burger King)' and unit[i] in ['1 cheeseburger']:
                        if "a classic Whopper with cheese" in query:
                            unit_in_query_new.append("a classic Whopper with cheese")
                        else:
                            print('a') 
                    elif description[i] == 'Cheeseburger (McDonalds)' and unit[i] in ['1 cheeseburger']:
                        if "my cheeseburger from McDonald's" in query:
                            unit_in_query_new.append("my cheeseburger from McDonald's")
                        else:
                            print('a') 
                    elif description[i] == 'Big Mac (McDonalds)' and unit[i] in ["1 McDonald's Big Mac"]:
                        if "a classic McDonald's Big Mac" in query:
                            unit_in_query_new.append("a classic McDonald's Big Mac")
                        else:
                            print('a') 
                    else:

                        print('b')
                else:
                    unit_in_query_new.append(unit_in_query[i])
            if not any([x for x in unit_in_query_new if x == '-1']) and len(unit_in_query_new)==len(unit_in_query):
                r['query_processed'] = query 
            else:
                fail_count_after_remove_special_cases += 1
                print(idx)
                print(r['description'])
                print(r['unit'])
                print(r['query_pass_food_name_check'])
                print(r['unit_in_query'])
                print(r['query_regenerated_for_unit'])
                print(r['unit_in_query_regenerated_for_unit'])
                print('-'*100)
                # with open('aaa.py', 'a') as f:
                #     f.write(f"    res_new[{idx}]['query_processed'] = \"{r['query_pass_food_name_check']}\"\n")
                # print(f"    res_new[{idx}]['query_processed'] = \"{r['query_pass_food_name_check']}\"")

    print(fail_count_after_remove_special_cases)
    assert fail_count_after_remove_special_cases == 0
    res_final = []
    for i, r in enumerate(res_new):
        if r['query_processed'] == "-1":
            continue
        elif r['query_processed'] == "":
            print(i)
            print(r['description'])
            print(r['unit'])
            print(r['query_pass_food_name_check'])
            print(r['unit_in_query'])
            print(r['query_regenerated_for_unit'])
            print(r['unit_in_query_regenerated_for_unit'])
            print('-'*100)
        else:
            res_final.append(r)
    print("len(res_final)", len(res_final))
    with open('/home/andong/NutriBench_FT/benchmark/query/meal_natural_query_processed.json', 'w') as f:
        json.dump(res_final, f, indent=4)