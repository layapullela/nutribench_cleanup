from openai import OpenAI
import os
import json

# you should run this file after running fix_missing_metrics.py (and maybe also double_fix_missing_metrics.py)

# Set up OpenAI API key from api_key.txt
with open('api_key.txt', 'r') as file:
    api_key = file.read().strip()

client = OpenAI(
    api_key=api_key,
)

def verify_meal_descriptions(description, unit, query, metric, who=True):
    # Combine descriptions and weights
    # Convert string representations of lists to actual lists if needed
    if isinstance(description, str):
        description = eval(description)
    if isinstance(unit, str):
        unit = eval(unit)
    
    # Clean up the unit strings and combine with descriptions
    meal_items = []
    for desc, amt in zip(description, unit):
        meal_items.append(f"{amt} {desc}")

    # Determine if there is only one meal item
    if len(meal_items) == 1:
        meal_items_str = meal_items[0]
        # if the prompt is "who": 
        if who:
            food_check_prompt = f"""
                Here is the description for you to check: {query}

                Does the description mention the meal item '{meal_items_str}' in any form, even if the wording is slightly different?
                The item may be described using a similar or common name. 

                Example:
                - Description: "I’m snacking on 125g of light starchy pudding."
                - Meal Item: 'Starchy pudding, QUALITATIVE-INFO = Light, PREPARATION-PRODUCTION-PLACE = Food industry prepared'
                - Since 'light starchy pudding' is mentioned, the correct response is: YES.

                If the item is present conceptually, output 'YES'. If it is missing, output 'NO'.
            """
            #breakpoint()
        else: 
            food_check_prompt = f"""
                Here is the description for you to check: {query}

                Does the description mention the meal item '{meal_items_str}' in any form, even if the wording is slightly different?
                The item may be described using a similar or common name. 

                Example:
                - Description: "I'm just having some bottled water as a snack."
                - Meal Item: 'Water, bottled, unsweetened'
                - Since 'water' is mentioned, the correct response is: YES.

                If the item is present conceptually, output 'YES'. If it is missing, output 'NO'.
            """
    else:
        meal_items_str = ' || '.join(meal_items)
        # in addition to '||', count off each item 
        count = 2
        while '||' in meal_items_str:
            meal_items_str = meal_items_str.replace('||', f'|{count}. ', 1)
            count += 1
        if who: 
            food_check_prompt = f"""
            Here is the description for you to check: {query}

            Does the description mention all {len(meal_items)} the meal items in any form, even if the wording is slightly different?
            The items may be described using alternative or common names. The {len(meal_items)} to check are: 1. {meal_items_str}.

            Example:
            - Description: "I’m snacking on 110g of mandarins and 125g of light starchy pudding."
            - Meal Items: Mandarins | Starchy pudding, QUALITATIVE-INFO = Light, PREPARATION-PRODUCTION-PLACE = Food industry prepared
            - Since 'mandarins' and 'light starchy pudding' are mentioned, the correct response is: YES.

            If ALL items are present conceptually, output 'YES'. If ANY item is missing, output 'NO'.
            """
            #breakpoint()
        else:
            food_check_prompt = f"""
                Here is the description for you to check: {query}

                Does the description mention all of the meal items in any form, even if the wording is slightly different?
                The items may be described using alternative or common names. The items to check are: {meal_items_str}.

                Example:
                - Description: "For dinner, I had a fried chicken drumstick, some cooked broccoli from the restaurant, and a fried chicken wing."
                - Meal Items: Chicken drumstick, fried, coated, skin / coating eaten, from pre-cooked ||  Broccoli, cooked, from restaurant || Chicken wing, fried, coated, from pre-cooked
                - Since 'fried chicken drumstick', 'cooked broccoli', and 'fried chicken wing' are mentioned in a natural way, the correct response is: YES.

                If ALL items are present conceptually, output 'YES'. If ANY item is missing, output 'NO'.
            """

    # Query ChatGPT for the first step
    food_check_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": food_check_prompt}]
    )

    # Extract response
    food_check_result = food_check_response.choices[0].message.content.strip()

    # print to console
    if food_check_result == 'NO':
        print("❌: Filtered query is incorrect")
    else: 
        print("✅: Filtered query is correct")

    return food_check_result

def process_json_objects(file_path): 
    with open(file_path, 'r') as file:
        data = json.load(file)

    metric = 'metric' in file_path

    for v, obj in enumerate(data):

        print(f"Object {v+1} of {len(data)}")
        description = obj.get('description')
        unit = obj.get('unit')
        #queries = obj.get('query')
        if obj.get('filtered_queries'): 
            queries = obj.get('filtered_queries')
        else:  
            queries = obj.get('revised_description')
            queries = { 
                "query_1": str(queries)
            }

        verifications = []

        # Convert queries string to dict if queries is a string
        if isinstance(queries, str):
            queries = eval(queries)

        for query_key, query_text in queries.items():
            verification = verify_meal_descriptions(description, unit, query_text, metric, 'who' in file_path)
            verifications.append(verification)
        
        obj['verification'] = verifications

    # Before the .json in filepath, add 'verification'
    file_path = file_path.replace('.json', '-verified.json')
    file_path = file_path.replace('revised_metrics', 'revised_metrics/item_verification')

    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def process_all_files_in_directory(directory):
    for filename in os.listdir(directory):
        if "metric" in filename and 'who_metric_ARG' in filename and filename.endswith('.json') and 'revised' in filename and not 'verified' in filename:
            file_path = os.path.join(directory, filename)
            process_json_objects(file_path)

if __name__ == "__main__":
    directory = 'new_prompt_queries/revised_metrics'
    process_all_files_in_directory(directory)


