from openai import OpenAI
import os
import json
import re

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

        pattern = r"\b(?:\d+(?:\.\d+)?|\d+/\d+|half(?:\s+a)?|a)\s?(?:-|\s)?(?:grams?|g(?:rams?)?)\b"
        matches = re.findall(pattern, query_text)
        rounded_units = [round(float(u.replace('g', '')), 1) for u in unit]

        list_of_weights = [] 
        print("query:", query_text)
        print("matches:", matches)
        print("unit:", unit)
        for m in matches:
            if "half" in m:
                list_of_weights.append(0.5)
                continue
            if "a " in m: 
                list_of_weights.append(1)
                continue
            # remove any letters from m (ignore decimal and or /)
            m = re.sub(r'[^\d./]', '', m)
            # if m is a fraction, convert it to a decimal  
            if '/' in m:
                num, denom = m.split('/')
                m = float(num) / float(denom)
            else:
                #print(m)
                m = float(m)
            list_of_weights.append(m)
        
        list_of_weights = [round(w, 1) for w in list_of_weights]
        temp = [l for l in list_of_weights] # for debug

        missing = False
        for v in rounded_units:
            if v in list_of_weights: 
                list_of_weights.remove(v)
            else: 
                missing = True

        if not missing: 
            filtered_queries[query_key] = query_text
    
    if len(filtered_queries) == 0:
        print("❌ No queries with metrics found")
        #breakpoint()
    else: 
        print("✅ Found queries with metrics")

    return filtered_queries

def create_revised_description(description, unit, query, tries=0):
    # Combine descriptions and weights
    if isinstance(description, str):
        description = eval(description)
    if isinstance(unit, str):
        unit = eval(unit)
    
    meal_items = []
    for desc, amt in zip(description, unit):
        meal_items.append(f"{amt} {desc}")

    # prompt for gpt for who queries
    prompt = (
        f"Here is the original description: {query}\n"
        "Please add the exact weights in grams for the following meal items without changing anything else in the description."
        "If any meal item is missing, include it in the description as well. Keep the descriptions of the meal items natural and informal. "
        "For example, instead of using 'Borlotti or other common beans (dry), PROCESS = Boiling, QUALITATIVE-INFO = Black', just write 'Borlotti beans' in the description. "
        f"Here are the meal items and metric portions to add: {', '.join(meal_items)}."
    )

    # prompt for gpt for american queries 
    # prompt = (
    #     f"Here is the original description: {query}\n"
    #     "Please add the exact weights in grams for the following meal items without changing anything else in the description. "
    #     "If any meal item is missing, include it in the description as well. Keep the descriptions of the meal items natural and informal."
    #     f"Here are the meal items and metric portions to add: {', '.join(meal_items)}."
    # )
    
    # Query ChatGPT
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract the revised description
    revised_description = response.choices[0].message.content.strip()

    query = { 
        "query_1": revised_description
    }

    #breakpoint()

    filtered_queries = filter_queries_with_metrics(description, str(unit), query)
    if not filtered_queries and tries < 3:
        revised_description = create_revised_description(description, unit, revised_description, tries + 1)
    if not filtered_queries and tries >= 3: 
        revised_description = "FIX ME: Unable to adjust the description automatically"

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
    revised_file_path = file_path.replace('.json', '-revised2.json')
    revised_file_path = revised_file_path.replace('new_prompt_queries', 'new_prompt_queries/revised_metrics')
    with open(revised_file_path, 'w') as file:
        json.dump(revised_data, file, indent=4)

def process_all_files_in_directory(directory):
    for filename in os.listdir(directory):
        if "metric" in filename and filename.endswith('.json') and not 'revised' in filename:
                file_path = os.path.join(directory, filename)
                process_json_objects(file_path)

if __name__ == "__main__":
    directory = 'new_prompt_queries'
    process_all_files_in_directory(directory)

    print(f"Adjusted {adjust} descriptions.")
