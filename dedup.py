import os
import json

def remove_duplicates_from_json(file_path):

    removed = 0

    with open(file_path, 'r') as file:
        data = json.load(file)
    
    seen = set()
    unique_data = []
    for item in data:
        meal_str = item.get('meal_str')

        # split the meal string by || to get the individual meal items
        meal_items = meal_str.split('||')
        meal_items = [item.strip() for item in meal_items]
        meal_items = sorted(meal_items)
        meal_str = '||'.join(meal_items)

        if meal_str not in seen:
            seen.add(meal_str)
            unique_data.append(item)
        else: 
            removed += 1
    
    with open(file_path, 'w') as file:
        json.dump(unique_data, file, indent=4)

    print(f'Removed {removed} duplicates from {file_path}')

def process_all_files_in_directory(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            file_path = os.path.join(directory, filename)
            remove_duplicates_from_json(file_path)

if __name__ == "__main__":
    directory = 'new_prompt_queries'
    process_all_files_in_directory(directory)

