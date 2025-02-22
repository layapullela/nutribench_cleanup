from openai import OpenAI
import os
import json

# Set up OpenAI API key from api_key.txt
with open('api_key.txt', 'r') as file:
    api_key = file.read().strip()

client = OpenAI(
    api_key=api_key,
)

adjust = 0

def filter_queries_with_metrics(description, unit, queries):
    filtered_queries = {}
    unit = eval(unit)
    for query_key, query_text in queries.items():
        missing = False
        for u in unit:
            grams = u.replace('g', '')
            grams = int(float(grams))
            if str(grams) not in query_text:
                missing = True
                break
        if not missing:
            filtered_queries[query_key] = query_text
    return filtered_queries

def create_revised_description(description, unit, query):
    # Combine descriptions and weights
    if isinstance(description, str):
        description = eval(description)
    if isinstance(unit, str):
        unit = eval(unit)
    
    meal_items = []
    for desc, amt in zip(description, unit):
        meal_items.append(f"{amt} {desc}")

    # Prepare the prompt for ChatGPT
    prompt = f"""
    Here is the original description: {query}
    Please add the exact weights in grams for the following meal items without changing anything else in the description. If any meal item is missing, you may include it in the description as well: {', '.join(meal_items)}.
    """

    # Query ChatGPT
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract the revised description
    revised_description = response.choices[0].message.content.strip()

    global adjust
    adjust += 1
    return revised_description

def process_json_objects(file_path): 
    with open(file_path, 'r') as file:
        data = json.load(file)

    count = 0
    revised_data = []
    total_objects = len(data)

    for obj in data:
        description = obj.get('description')
        unit = obj.get('unit')
        queries = obj.get('query')
        
        if isinstance(queries, str):
            queries = eval(queries)

        filtered_queries = filter_queries_with_metrics(description, unit, queries)

        if not filtered_queries:
            # If no queries have metrics, create a revised description
            revised_description = create_revised_description(description, unit, queries[list(queries.keys())[0]])
            obj['revised_description'] = revised_description
        else:
            obj['filtered_queries'] = filtered_queries

        revised_data.append(obj)
        count += 1

        # Print percentage of processing done
        if count % 10 == 0 or count == total_objects:
            print(f"Processing: {count / total_objects * 100:.2f}% done")

    # Save the revised data to a new file
    revised_file_path = file_path.replace('.json', '-revised.json')
    revised_file_path = revised_file_path.replace('new_prompt_queries', 'new_prompt_queries/revised_metrics')
    with open(revised_file_path, 'w') as file:
        json.dump(revised_data, file, indent=4)

def process_all_files_in_directory(directory):
    for filename in os.listdir(directory):
        if "metric" in filename and filename.endswith('.json') and not 'revised' in filename and not 'meal' in filename:
        #if "metric" in filename and not "who" in filename:  
            file_path = os.path.join(directory, filename)
            process_json_objects(file_path)

if __name__ == "__main__":
    directory = 'new_prompt_queries'
    process_all_files_in_directory(directory)

    print(f"Adjusted {adjust} descriptions.")
