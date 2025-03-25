# Nutribench_v2 Dataset

## Overview
The `nutribench_v2.csv` dataset is an international collection of meal descriptions, nutritional information, and associated metadata. 

## Dataset Structure
The dataset contains the following columns:
- `description`: A list of textual descriptions of each meal item in the meal.
- `carb`: The carbohydrate content of the meal (in grams).
- `fat`: The fat content of the meal (in grams).
- `energy`: The energy content of the meal (in kilocalories).
- `protein`: The protein content of the meal (in grams).
- `country`: The country associated with the meal. (USA meals are from WWEIA dataset, international meals from WHO datasets)
- `amount_type`: Indicates whether the measurements are in metric units (`metric`) or natural units (`natural`).
- `queries`: A natural language description of the meal.

## Acknowledgements
Laya Pullela Sophia Mirrashidi processed and manually verified these data to compile nutribench_v2.

## License
This dataset is provided under the [MIT License](https://opensource.org/licenses/MIT).