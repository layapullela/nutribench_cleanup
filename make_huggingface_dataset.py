import os
import pandas as pd
import json
import random

def consolidate_datasets(directory):
    data_frames = []
    for folder in os.listdir(directory):
        folder_path = os.path.join(directory, folder)
        if os.path.isdir(folder_path):
            amount_type = 'metric' if 'metrics' in folder else 'natural'
            for filename in os.listdir(folder_path):
                if filename.endswith(".json"):
                    file_path = os.path.join(folder_path, filename)
                    with open(file_path, 'r') as file:
                        data = json.load(file)
                        df = pd.json_normalize(data)
                        df['amount_type'] = amount_type
                        if amount_type == 'metric' and 'meal_metric_queries' not in file_path:
                            country = filename.split('_')[2].split('-')[0]
                        else:
                            country = 'USA'
                        df['country'] = country
                        
                        # Add queries column
                        queries = []
                        for item in data:
                            filtered_queries = item.get('filtered_queries', {})
                            if filtered_queries:
                                queries.append(random.choice(list(filtered_queries.values())))
                            else:
                                queries.append(item.get('revised_description', ''))
                        df['queries'] = queries
                        
                        data_frames.append(df)
    
    consolidated_df = pd.concat(data_frames, ignore_index=True)
    return consolidated_df

def main():
    directory = "new_prompt_queries"
    consolidated_df = consolidate_datasets(directory)
    
    # Select the required columns
    required_columns = ['description', 'carb', 'fat', 'energy', 'protein', 'country', 'amount_type', 'queries']
    consolidated_df = consolidated_df[required_columns]
    
    # Save the consolidated dataset to a new CSV file
    consolidated_df.to_csv("nutribench_v2.csv", index=False)

if __name__ == "__main__":
    main()
