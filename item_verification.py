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

with open('sugar_reductions.txt', 'r') as f:
    sugar_reductions = f.readlines()
    sugar_reductions = [x.strip() for x in sugar_reductions]

def verify_meal_descriptions(description, unit, query, metric, who=True):
    # Convert string representations of lists to actual lists if needed
    if isinstance(description, str):
        description = eval(description)
    if isinstance(unit, str):
        unit = eval(unit)
    
    # Clean up the unit strings and combine with descriptions
    verifications = []
    for desc, amt in zip(description, unit):
        #meal_item_combined = f"{amt} {desc}"

        if metric: 
            if who:
                food_check_prompt = (
                    f"Here is the description for you to check: {query}\n\n"
                    f"Does the description mention the meal item '{desc}' in any form, even if the wording is slightly different?\n"
                    "The item may be described using a similar or common name.\n\n"
                    "Example:\n"
                    "- Description: \"I'm snacking on a cup of light starchy pudding, 2 servings of fruit, and 1 bottle of water.\"\n"
                    "- Meal Item: '125g Starchy pudding, QUALITATIVE-INFO = Light, PREPARATION-PRODUCTION-PLACE = Food industry prepared'\n"
                    "- Since a cup of light starchy pudding' is mentioned, the correct response is: YES.\n\n"
                    "If the item is present conceptually with the correct portion, output 'YES'. If it is missing or has wrong portion, output 'NO'."
                )
            else:
                food_check_prompt = (
                    f"Here is the description for you to check: {query}\n\n"
                    f"Does the description mention the meal item '{desc}' in any form, even if the wording is slightly different?\n"
                    "The item may be described using a similar or common name.\n\n"
                    "Example:\n"
                    "- Description: \"I've got a lunch that includes 240 grams of water, a thin crust pepperoni pizza slice from school at 142 grams, and 248 grams of ready-to-drink reduced sugar chocolate milk.\"\n"
                    "- Meal Item: 'Water, bottled, unsweetened'\n"
                    "- Since 'water' is mentioned, the correct response is: YES.\n"
                    "- If instead of unsweetened water, the description mentions sweetened water, the correct response is: NO, because sweetened water significantly changes the carbohydrate content.\n\n"
                    "If the item is present conceptually with the correct portion, output 'YES'. If it is missing or has wrong portion, output 'NO'."
                )
        else:
            lower_unit = amt.lower()
            lower_desc = desc.lower()

            # find which word is in the amt and make sure its in the query
            sizes = ['mini', 'miniature', 'small', 'medium', 'large']
            for size in sizes:
                if size in lower_unit and size not in query:
                    verifications.append("NO")
                    break

            global sugar_reduction 
            for sugar_reduction in sugar_reductions:    
                if sugar_reduction in lower_desc and sugar_reduction not in query:
                    if sugar_reduction == "sugar free" and "sugar-free" in query:
                        continue
                    if (sugar_reduction == "unsweetened" or sugar_reduction == "sweetened") and "water" in lower_desc: 
                        continue
                    verifications.append("NO")
                    break

            food_check_prompt = f"""
            Determine if the sentence contains the specified meal item and portion.

            Check:
            - Meal Item: {desc}
            - Portion: {amt}

            Sentence: {query}

            Rules:
            - It is okay if sentence does not contain all details of the meal item, as long as it is clearly mentioned. The portion should be clearly mentioned ('1 tbsp. of ketchup' instead of 'some ketchup'), but may be summarized or expressed with a common name (e.g. '1 cup of water' can be expressed as 'a glass of water', 'a single serving bag' can be summarized as 'a bag').

            Output:
            - YES: if the meal item and its portion are present.
            - NO: otherwise.
            """

        food_check_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": food_check_prompt}]
        )

        # Extract response
        food_check_result = food_check_response.choices[0].message.content.strip()
        verifications.append(food_check_result)

    # print to console
    if "NO" in verifications:
        print(f"❌: Query contains incorrect meal item or incorrect portion")
    else: 
        print(f"✅: Query contains correct meal item and correct portion")

    return "NO" if "NO" in verifications else "YES"

def process_json_objects(file_path): 
    # Create output filepath
    output_file_path = file_path.replace('.json', '-verified.json')
    output_file_path = output_file_path.replace('revised_metrics', 'revised_metrics/item_verification')
    
    # Read total length first
    with open(file_path, 'r') as file:
        total_length = len(json.load(file))

    # Check if output directory exists, if not create it
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
    
    # Check if file exists
    if not os.path.exists(output_file_path):
        # Create new file and write opening bracket
        with open(output_file_path, 'w') as outfile:
            outfile.write('[\n')
    else:
        # Append to existing file
        with open(output_file_path, 'a') as outfile:
            outfile.write(',\n')

    metric = 'natural' not in file_path

    # Read input file again to process objects
    with open(file_path, 'r') as file:
        data = json.load(file)
        for v, obj in enumerate(data):
            
            print(f"Object {v+1} of {total_length}")
            
            description = obj.get('description')
            unit = obj.get('unit')
            
            if metric: 
                if obj.get('filtered_queries'): 
                    queries = obj.get('filtered_queries')
                else:  
                    queries = obj.get('revised_description')
                    queries = { 
                        "query_1": str(queries)
                    }
            else: 
                queries = obj.get('query')

            verifications = []

            # Convert queries string to dict if queries is a string
            if isinstance(queries, str):
                queries = queries.replace('“', '"').replace('”', '"')
                queries = eval(queries)

            for query_key, query_text in queries.items():
                verification = verify_meal_descriptions(description, unit, query_text, metric, 'who' in file_path)
                verifications.append(verification)
            
            obj['verification'] = verifications

            # Write object to file
            with open(output_file_path, 'a') as outfile:
                json.dump(obj, outfile, indent=4)
                if v < total_length - 1:  # If not last object
                    outfile.write(',\n')
                else:  # If last object
                    outfile.write('\n')

    # Write closing bracket
    with open(output_file_path, 'a') as outfile:
        outfile.write(']')

def process_all_files_in_directory(directory):
    for filename in os.listdir(directory):
        if "natural" in filename and filename.endswith('.json') and not 'verified' in filename:
            file_path = os.path.join(directory, filename)
            process_json_objects(file_path)

if __name__ == "__main__":
    directory = 'new_prompt_queries/revised_metrics'
    process_all_files_in_directory(directory)


