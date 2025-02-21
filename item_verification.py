from openai import OpenAI
import os
import json

# Set up OpenAI API key from api_key.txt
with open('api_key.txt', 'r') as file:
    api_key = file.read().strip()

client = OpenAI(
    api_key=api_key,
)

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
    
    # Prepare the prompt for ChatGPT
    if metric: 
        prompt = f"Here is the description for you to check: {query} Can you make sure it contains the following meal items and specifies the exact weight in grams for each item: {', '.join(meal_items)}. Simply output 'YES' for correct and 'NO' for incorrect."
    else: 
        prompt = f"Here is the description for you to check: {query} Can you make sure it contains the following meal items and specifies the portion: {', '.join(meal_items)}. Simply output 'YES' for correct and 'NO' for incorrect."

    # Query ChatGPT
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract "YES" or "NO" from the response
    response_text = response.choices[0].message.content.strip()

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

        print("count: ", count)
        count += 1

    # before the .json in filepath, add 'verification'
    file_path = file_path.replace('.json', '-verification-2.json')

    with open(file_path, 'w') as file:
        json.dump(data[0:count], file, indent=4)

# look at the entire directory
def process_all_files_in_directory(directory):
    for filename in os.listdir(directory):
        if not 'who' in filename and filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            process_json_objects(file_path)

if __name__ == "__main__":
    directory = 'new_prompt_queries'
    process_all_files_in_directory(directory)


