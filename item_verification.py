from openai import OpenAI
import os
import json

# Set up OpenAI API key from api_key.txt
with open('api_key.txt', 'r') as file:
    api_key = file.read().strip()

client = OpenAI(
    api_key=api_key,
)

wrong = 0
# test with gpt

def verify_meal_descriptions(description, unit, query, metric):
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

    # uncomment
    # # Determine if there is only one meal item
    # if len(meal_items) == 1:
    #     meal_items_str = meal_items[0]
    #     food_check_prompt = f"""
    #         Here is the description for you to check: {query}

    #         Step 1: Does the description mention the meal item '{meal_items_str}' in any form, even if the wording is slightly different?
    #         The item may be described using a similar or common name. 

    #         Example:
    #         - Description: "I'm just having some bottled water as a snack."
    #         - Meal Item: 'Water, bottled, unsweetened'
    #         - Since 'water' is mentioned, the correct response is: YES.

    #         If the item is present conceptually, output 'YES'. If it is missing, output 'NO'.
    #     """
    # else:
    #     meal_items_str = ' || '.join(meal_items)
    #     food_check_prompt = f"""
    #         Here is the description for you to check: {query}

    #         Step 1: Does the description mention all of the meal items in any form, even if the wording is slightly different?
    #         The items may be described using alternative or common names. The items to check are: {meal_items_str}.

    #         Example:
    #         - Description: "For dinner, I had a fried chicken drumstick, some cooked broccoli from the restaurant, and a fried chicken wing."
    #         - Meal Items: Chicken drumstick, fried, coated, skin / coating eaten, from pre-cooked ||  Broccoli, cooked, from restaurant || Chicken wing, fried, coated, from pre-cooked
    #         - Since 'fried chicken drumstick', 'cooked broccoli', and 'fried chicken wing' are mentioned in a natural way, the correct response is: YES.

    #         If ALL items are present conceptually, output 'YES'. If ANY item is missing, output 'NO'.
    #     """

    # # Query ChatGPT for the first step
    # food_check_response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[{"role": "user", "content": food_check_prompt}]
    # )

    # Extract response
    #food_check_result = food_check_response.choices[0].message.content.strip()

    food_check_result = "YES" # uncomment

    unit_correct = False
    if food_check_result == "YES":
    # Step 2: Verify if units/portions match
        if metric:
            # check if unit[0] is in the prompt
            if len(meal_items) == 1:
                grams = unit[0].replace('g', '')
                grams = int(float(grams))
                # check if str(grams) is in the query
                if str(grams) in query: 
                    unit_correct = True
            else:
                # do the above logic for every item in meal_items
                missing = False
                for u in unit:
                    grams = u.replace('g', '')
                    grams = int(float(grams))
                    if str(grams) not in query:
                        missing = True
                unit_correct = not missing
        else:
            if len(meal_items) == 1:
                unit_check_prompt = f"""
                Description: {query}

                Step 2: Does the description specify this portion for the food item: '{meal_items[0]}'? 
                - If the correct portion is mentioned, return 'YES'.
                - Otherwise, return 'NO'.
                """
            else:
                unit_check_prompt = f"""
                Description: {query}

                Step 2: Here are the correct portions for each food item: {' || '.join(meal_items)}. Are these portions correctly specified in the description?
                - If all items have correct portions, return 'YES'.
                - If any item is missing or has an incorrect portion, return 'NO'.
                """


        # Query ChatGPT for the second step
        if not metric:
            unit_check_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": unit_check_prompt}]
            )
            unit_check_result = unit_check_response.choices[0].message.content.strip()
        else: 
            unit_check_result = "YES" if unit_correct else "NO_UNIT"

        if unit_check_result == "YES":
            print("✅ The description is correct.")
            response_text = "YES"
        else:
            print("❌ The description contains all meal items but has incorrect or missing portion sizes.")
            response_text = "NO_UNIT"
    else:
        print("❌ The description is missing some meal items.")
        response_text = "NO_ITEM"

    return response_text

def process_json_objects(file_path): 

    with open(file_path, 'r') as file:
        data = json.load(file)

    count = 0

    metric = 'metric' in file_path

    for obj in data:

        if count >= 100: 
            break

        description = obj.get('description')
        unit = obj.get('unit')
        queries = obj.get('query')
        
        verifications = []

        # convert queries string to dict if queries is a string
        if isinstance(queries, str):
            queries = eval(queries)

        for query_key, query_text in queries.items():
            verification = verify_meal_descriptions(description, unit, query_text, metric)
            verifications.append(verification)
        
        obj['verification'] = verifications

        # if all elements of verification is NO, add to wrong
        if all([v == 'NO_UNIT' for v in verifications]):
            global wrong
            wrong += 1

        print("count: ", count)
        count += 1

    # before the .json in filepath, add 'verification'

    # uncomment
    # file_path = file_path.replace('.json', '-verification.json')

    # with open(file_path, 'w') as file:
    #     json.dump(data[0:count], file, indent=4)

# look at the entire directory
def process_all_files_in_directory(directory):
    global wrong
    for filename in os.listdir(directory):
        #if "metric" in filename and filename.endswith('.json') and not 'verification' in filename: # uncomment
        #if "test" in filename: 
        if "who_metric_ARG" in filename:
            file_path = os.path.join(directory, filename)
            process_json_objects(file_path)

    print("wrong: ", wrong)

if __name__ == "__main__":
    directory = 'new_prompt_queries'
    process_all_files_in_directory(directory)


