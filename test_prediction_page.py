#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Prediction.py without Streamlit UI
Validates that the prediction model can be used correctly
"""

import sys
import io
from pathlib import Path

# Set up path
project_root = Path.cwd()
sys.path.insert(0, str(project_root))

# Fix for Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print('=' * 60)
    print('PREDICTION PAGE FUNCTIONALITY TEST')
    print('=' * 60)
    print()

    # Step 1: Test model loading
    print('Step 1: Testing LightGBM model loading...')
    try:
        from app import prediction_model_lightgbm as pml

        model = pml.get_advanced_prediction_model()
        print(f'✓ Model loaded: {model.model_name}')
        print(f'✓ Model trained: {model.is_trained}')

    except Exception as e:
        print(f'✗ Model loading failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Test queries module
    print()
    print('Step 2: Testing query functions...')
    try:
        from app import queries

        # Get race dates
        dates = queries.get_all_race_dates()
        if dates:
            print(f'✓ Found {len(dates)} race dates')
            test_date = dates[0]
            print(f'  Testing with date: {test_date}')

            # Get courses for this date
            courses = queries.get_courses_by_date(test_date)
            if courses:
                print(f'✓ Found {len(courses)} courses for {test_date}')
                test_course = courses[0]

                # Get races
                races = queries.get_races(test_date, test_course)
                if races:
                    print(f'✓ Found {len(races)} races for {test_date} at {test_course}')
                    test_race_id = races[0]['race_id']

                    # Get entries with metrics
                    entries = queries.get_race_entries_with_metrics(test_race_id)
                    if entries:
                        print(f'✓ Found {len(entries)} entries for race {test_race_id}')
                    else:
                        print('✗ No entries found for test race')
                        return False
                else:
                    print('✗ No races found')
                    return False
            else:
                print('✗ No courses found for test date')
                return False
        else:
            print('✗ No race dates found')
            return False

    except Exception as e:
        print(f'✗ Query test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Test prediction
    print()
    print('Step 3: Testing race order prediction...')
    try:
        horse_ids = [e['horse_id'] for e in entries if e['horse_id']]
        if not horse_ids:
            print('✗ No valid horse IDs found')
            return False

        print(f'  Predicting for {len(horse_ids)} horses...')

        # Get race info
        race = next((r for r in races if r['race_id'] == test_race_id), None)
        race_info = {
            'distance_m': race.get('distance_m') if race else 0,
            'surface': race.get('surface') if race else '',
        } if race else None

        # Run prediction
        results = model.predict_race_order(horse_ids[:10], race_info=race_info)

        if 'predictions' in results:
            predictions = results['predictions']
            print(f'✓ Prediction completed for {len(predictions)} horses')
            print(f'  Model type: {results.get("model_type")}')

            if predictions:
                top_pred = predictions[0]
                print(f'  Top prediction: {top_pred["horse_name"]} (confidence: {top_pred["confidence"]:.1f}%)')
        elif 'error' in results:
            print(f'✗ Prediction error: {results["error"]}')
            return False
        else:
            print('✗ Unknown prediction result format')
            return False

    except Exception as e:
        print(f'✗ Prediction test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    print()
    print('=' * 60)
    print('ALL PREDICTION TESTS PASSED ✓')
    print('=' * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
