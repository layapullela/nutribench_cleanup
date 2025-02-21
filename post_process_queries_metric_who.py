import json
import copy
import random
import re
import ast
from openai import OpenAI
import os
from apikey import openai_apikey
from tqdm import tqdm
from post_process_queries_natural import split_queries_random_pick, improve_food_name, check_food_names


def check_food_units(r, key='query_pass_food_name_check'):
    units_number_list = ast.literal_eval(r['unit_weight'])
    real_units = []
    sucess = True
    for unit in units_number_list:
        if str(int(unit)) in r[key] or (unit==0.5 and 'half a gram'in r[key]):
            real_units.append(str(int(unit)))
        else:
            real_units.append("-1")
            sucess = False
    return sucess, real_units


if __name__ == '__main__':
    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # automatic check food names

    # random.seed(0)
    # os.environ["OPENAI_API_KEY"] = openai_apikey
    # client = OpenAI()

    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query.json') as f:
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

    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_v1.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # manually check the remaining food items
    # path = '/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_v1.json'
    # with open(path) as f:
    #     res = json.load(f)
    # res_new = copy.deepcopy(res)

    # res_new[269]['query_pass_food_name_check'] = "-1"
    # res_new[373]['query_pass_food_name_check'] = "-1"
    # res_new[439]['query_pass_food_name_check'] = "I enjoyed 47.8g boiled eggs, 3.9g vegetable, and a 69.2g tortilla with 0.2g salt and 10.1g sugar. In addition, I hvae 36.2g strawberries and 172.6g cow milk."

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

    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_v2.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)


    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # automatic check food units
    # random.seed(0)
    # os.environ["OPENAI_API_KEY"] = openai_apikey
    # client = OpenAI()

    # path = '/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_v2.json'
    # with open(path) as f:
    #     res = json.load(f)
    # res_new = copy.deepcopy(res)

    # fail_count = 0
    # for i, r in enumerate(res_new):
    #     sucess, real_units = check_food_units(r)
    #     r['unit_in_query'] = real_units
    #     if not sucess:
    #         # automatic improve the food unit
    #         fail_count += 1
    #         print(i)
    #         print(r['description'])
    #         print(r['unit'])
    #         print(r['query_pass_food_name_check'])
    #         print(real_units)
    #         print('-'*100)
    #         # print(f"    res_new[{i}]['query_processed'] = \"{r['query_pass_food_name_check']}\"")
    #         r['query_processed'] = ""
    #     else:
    #         r['query_processed'] = r['query_pass_food_name_check']
    # print("fail_count: ", fail_count)

    # res_new[167]['query_processed'] = "For a light snack, I had 146.25g rice, 102.75g of enriched white bread, 180g of raw orange, and finished it off with 105g of fresh pears."
    # res_new[269]['query_processed'] = "-1"
    # res_new[373]['query_processed'] = "-1"
    # res_new[399]['query_processed'] = "-1"
    # res_new[416]['query_processed'] = "-1"
    # res_new[422]['query_processed'] = "-1"
    # res_new[472]['query_processed'] = "-1"
    # res_new[474]['query_processed'] = "-1"
    # res_new[496]['query_processed'] = "For dinner, I had 60g of fortified Frankfurter sausage alongside a savory meat stew made with 105.6g of ham, boiled potatoes, and diced carrots. In addition, I had 85.0g pasta with 106.6g meat balls"

    # res_final = []
    # for i, r in enumerate(res_new):
    #     if r['query_processed'] == "-1":
    #         continue
    #     else:
    #         sucess, real_units = check_food_units(r, key='query_processed')
    #         assert sucess
    #         r.pop('Unnamed: 0')
    #         r.pop('index')
    #         res_final.append(r)

    # print("res final len: ", len(res_final))   
    # with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_processed.json', 'w') as f:
    #     json.dump(res_final, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # remove invalid queries in metric and natural data
    metric_path = '/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_processed.json'
    natural_path = '/home/andong/NutriBench_FT/benchmark/query/who_meal_natural_query_processed.json'
    with open(metric_path) as f:
        metric_data = json.load(f)
    with open(natural_path) as f:
        natural_data = json.load(f)


    metric_data_new = []
    for i in range(len(metric_data)):
        if i in [95, 96, 205]:
            continue
        metric_data_new.append(metric_data[i])

    for i in range(min(len(metric_data_new), len(natural_data))):
        if metric_data_new[i]['description'] != natural_data[i]['description']:
            print(metric_data_new[i]['description'])
            print(natural_data[i]['description'])
            print(i)
    print("metric_data_new", len(metric_data_new))
    with open('/home/andong/NutriBench_FT/benchmark/query/who_meal_metric_query_processed.json', 'w') as f:
        json.dump(metric_data_new, f, indent=4)
    print('done')