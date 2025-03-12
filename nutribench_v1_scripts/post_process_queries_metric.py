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

    # with open('/home/andong/NutriBench_FT/benchmark/query/meal_metric_query.json') as f:
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

    # with open('/home/andong/NutriBench_FT/benchmark/query/meal_metric_query_v1.json', 'w') as f:
    #     json.dump(res_new, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # automatic check food units
    random.seed(0)
    os.environ["OPENAI_API_KEY"] = openai_apikey
    client = OpenAI()

    path = '/home/andong/NutriBench_FT/benchmark/query/meal_metric_query_v1.json'
    with open(path) as f:
        res = json.load(f)
    res_new = copy.deepcopy(res)

    fail_count = 0
    for i, r in enumerate(res_new):
        sucess, real_units = check_food_units(r)
        r['unit_in_query'] = real_units
        if not sucess:
            # automatic improve the food unit
            fail_count += 1
            print(i)
            print(r['description'])
            print(r['unit'])
            print(r['query_pass_food_name_check'])
            print(real_units)
            print('-'*100)
            # print(f"    res_new[{i}]['query_processed'] = \"{r['query_pass_food_name_check']}\"")
            r['query_processed'] = ""
        else:
            r['query_processed'] = r['query_pass_food_name_check']
    print("fail_count: ", fail_count)

    res_new[8]['query_processed'] = "My lunch featured 35g sauteed chicken wings, 60g of skin-on sautéed chicken drumsticks, paired with 250g of fluffy mashed potatoes and a generous 17g serving of ketchup."
    res_new[118]['query_processed'] = "-1"
    res_new[203]['query_processed'] = "During my lunch, I enjoyed 38g cookie, 262g nachos with meat and cheese, 28g of onion-flavored rings, paired with a refreshing 620g Powerade sports drink."
    res_new[224]['query_processed'] = "For breakfast, I had a delicious 150g low-fat yogurt parfait with fruit, complemented by a sprinkle of 3.5g of granulated sugar, and enjoyed it alongside 480g coffee with 30g of half and half."
    res_new[406]['query_processed'] = "For breakfast this morning, I enjoyed a delightful 240g of hot herbal tea, 92g of sardines canned in oil, a perfectly boiled egg weighing 50g, and 33g toasted whole wheat bread topped with 20g of honey. To complete my meal, I savored 17g of rich Cheddar cheese, all while sipping on 240g refreshing tap water."
    res_new[929]['query_processed'] = "For lunch, I had a 73g white hoagie roll filled with 263g succulent ham slathered in barbecue sauce, accompanied by 240g of refreshing bottled water."
    res_new[1184]['query_processed'] = "For a satisfying snack, I savored 250g tomato-based pasta with meat, 108g of buttery corn and 55g of grilled chicken wings, while sipping on a chilled 372g cola."
    res_new[1264]['query_processed'] = "For lunch, I had a delightful 14.2g of milk chocolate candy with 24g cereal, paired with a 56g peanut butter and jelly sandwich on white bread and 186g fruit juice."
    res_new[1634]['query_processed'] = "For lunch, I savored a 70g fast food biscuit, 55g of fried chicken wings, 110g chicken tigh and 145g french fries."
    res_new[1981]['query_processed'] = "-1"
    res_new[1995]['query_processed'] = "Tonight's dinner featured 98g of delicious cheese pizza and 105g of pepperoni pizza from a local restaurant."
    res_new[2132]['query_processed'] = "During my afternoon snack, I savored 75g chocolate doughnut with 28g cheese flavored corn snacks, as well as 153g of a frosted cinnamon bun roll and a tasty 17g Reese's Peanut Butter Cup."
    res_new[2719]['query_processed'] = "During my snack time, I enjoyed a 53g nut roll, 110g french fries, 100g McDonald's hamburger along with 28g of ruffled sour cream and onion flavored potato chips."
    res_new[2852]['query_processed'] = "For dinner tonight, I indulged in 217g beef and vegetables with soy-based sauce and 252g of orange chicken, served with 166g of meatless fried rice and a large 620g bottle of iced black tea."
    res_new[2876]['query_processed'] = "During brunch, I enjoyed 124g of medium crust pepperoni pizza and 138g medium crust pizza with other meat, fresh from my favorite fast food spot."
    res_new[3031]['query_processed'] = "During dinner, I enjoyed a 44g snack chocolate cake and a refreshing 507g of bottled water, accompanied by a 75g Italian sausage and a 45g white hot dog bun, with a hint of 5g mustard for extra flavor."
    res_new[3059]['query_processed'] = "At lunch, I treated myself to a 117g soft taco with meat, enhanced by 30g of smooth and tangy regular sour cream."
    res_new[3289]['query_processed'] = "For my lunch, I savored a 507g serving of low-calorie sports drink, alongside a 145g turkey burger on a wheat bun, which was topped with 17g of ketchup and a hint of 5g mustard."
    res_new[3326]['query_processed'] = "For lunch, I had 248g of ready-to-drink whole chocolate milk, a refreshing 154g raw orange, a 42g cereal bar, a 112g peanut butter and jelly sandwich, a crunchy 42g General Mills Nature Valley granola bar and 200g apple."
    res_new[3433]['query_processed'] = "During my snack time, I enjoyed 24g Quaker Chewy Granola bar, 68g Clif Bar, a 16g serving of peanut butter, and a 126g banana."
    res_new[3484]['query_processed'] = "For dinner, I had a delicious cheeseburger on a wheat bun with a medium patty, weighing 165g, topped with 17g of ketchup and 5g of mustard."
    res_new[3550]['query_processed'] = "I savored a 135g taco with meat, 248g meat Burrito with beans and 133g tostada with meat, alongside with sour cream for dinner tonight."
    res_new[3576]['query_processed'] = "Today's lunch consisted of 200g Quarter Pounder cheeseburger and 300g of delicious soft serve mixed with candy and cookies, paired with 145g of french fries and a 744g caffeine-free fruit-flavored soft drink."
    res_new[3760]['query_processed'] = "For my lunch, I had 248g of ready-to-drink reduced sugar chocolate milk, paired with a 112g peanut butter and jelly sandwich, a crispy 40g of raw celery, and 165g apple."
    res_new[4117]['query_processed'] = "For my snack, I had 240g of brewed iced coffee with 15g of flavored liquid coffee creamer, adding a delightful touch."
    res_new[4372]['query_processed'] = "This morning, I enjoyed a filling breakfast of 226g of egg, cheese, ham, and bacon on a bun, accompanied by 55g of delicious hash browns from the fast food place. To complement my meal, I added 9g taco sauce for some extra flavor. While savoring my meal, I sipped on 360g of brewed coffee, sweetened with 3.5g of white granulated sugar and enriched with 30g of half-and-half cream for a delightfully creamy finish."
    res_new[4545]['query_processed'] = "-1"
    res_new[4581]['query_processed'] = "For a quick snack, I indulged in a 150g raw peach and 240g of sweet gelatin dessert, paired with 35g chocolate cereal bar and 507g of crisp bottled water."
    res_new[4681]['query_processed'] = "During my afternoon snack, I enjoyed a 93g piece of pan dulce topped with sugar and 360g of freshly brewed coffee with 15g half and half cream, sweetened with just a hint of 1g sucralose."
    res_new[4894]['query_processed'] = "-1"
    res_new[4949]['query_processed'] = "My snack consisted of 100g of a juicy McDonald's hamburger, 28g of flavorful potato chips, 110g french fries and 53g of a nut roll packed with fudge, nougat, caramel, and nuts, making for a satisfying treat."
    res_new[5013]['query_processed'] = "I started my day with a 159g English muffin with egg, cheese and sausage. I also had 168g egg, cheese, and bacon sandwich on a griddle cake and a 620g glass of ginger ale for a bubbly touch."
    res_new[5221]['query_processed'] = "-1"
    res_new[5413]['query_processed'] = "For lunch, my meal consisted of a delicious 112g peanut butter and jelly sandwich made with regular peanut butter, regular jelly, and hearty wheat bread. I also enjoyed a 57g serving of nacho cheese-flavored Doritos tortilla chips, a substantial 186g fruit juice blend for a refreshing drink, and a delightful 14g portion of fruit leather, providing a sweet finish to my meal. To round it all off, I savored a 30g oatmeal cookie, adding a comforting touch to my lunch."
    res_new[5607]['query_processed'] = "For lunch, I treated myself to an 88g corn dog accompanied by 14.7g of creamy dressing for dipping, a satisfying 245g serving of low-fat yogurt with fruit, and a classic 116g grilled cheese sandwich made with American cheese on white bread. To wash it all down, I enjoyed a 360g refreshing bottle of unsweetened water."
    res_new[5753]['query_processed'] = "I treated myself to a delightful snack of 248g cafe con leche coffee, enhanced with half a gram of sucralose."
    res_new[6155]['query_processed'] = "-1"
    res_new[6551]['query_processed'] = "For dinner today, I savored a 438g meat burrito, finished off with 0.3g fresh cilantro for that extra zest."
    res_new[6889]['query_processed'] = "-1"
    res_new[6906]['query_processed'] = "For dinner, I had 57g of beef frankfurter in a 52 soft white roll, accompanied by 254g of chili con carne without beans."

    res_final = []
    for i, r in enumerate(res_new):
        if r['query_processed'] == "-1":
            continue
        else:
            sucess, real_units = check_food_units(r, key='query_processed')
            assert sucess
            res_final.append(r)

    print("res final len: ", len(res_final))   
    with open('/home/andong/NutriBench_FT/benchmark/query/meal_metric_query_processed.json', 'w') as f:
        json.dump(res_final, f, indent=4)

    # ------------------------------------------------------------------------------------------------------------------------------------ #
    # manually check the remaining food items
