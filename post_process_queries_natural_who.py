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

    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query.json') as f:
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

    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query_v1.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # automatic check food units
    # random.seed(0)
    # os.environ["OPENAI_API_KEY"] = openai_apikey
    # client = OpenAI()

    # path = '/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query_v1.json'
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
    
    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query_v3.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # manually check the remaining food items

    path = '/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query_v3.json'
    with open(path) as f:
        res = json.load(f)
    res_new = copy.deepcopy(res)

    fail_count = len([r for r in res_new if r['query_processed'] == ""])
    print(fail_count)

    # manual modification
    res_new[95]['query_processed'] = "-1"
    res_new[96]['query_processed'] = "-1"
    res_new[103]['query_processed'] = "During snack time, I enjoyed a chocolate croissant alongside two refreshing bottles of liquid yogurt."
    res_new[205]['query_processed'] = "-1"



    fail_count_after_remove_special_cases = 0
    for idx, r in tqdm(enumerate(res_new)):
        if r['query_processed'] == "":
            fail_count_after_remove_special_cases += 1
            print(idx)
            print(r['description'])
            print(r['unit'])
            print(r['query_pass_food_name_check'])
            print(r['unit_in_query'])
            print(r['query_regenerated_for_unit'])
            print(r['unit_in_query_regenerated_for_unit'])
            print('-'*100)

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
            r.pop('Unnamed: 0')
            r.pop('index')
            res_final.append(r)
    print("len(res_final)", len(res_final))
    with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query_processed.json', 'w') as f:
        json.dump(res_final, f, indent=4)