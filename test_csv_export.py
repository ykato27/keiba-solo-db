#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CSVエクスポート機能のテスト
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
    print('CSV EXPORT TEST')
    print('=' * 60)
    print()

    # Step 1: Test imports
    print('Step 1: Testing imports...')
    try:
        from app import csv_export, queries
        print('✓ Imports successful')
    except Exception as e:
        print(f'✗ Import failed: {e}')
        return False

    # Step 2: Get sample race
    print()
    print('Step 2: Getting sample race...')
    try:
        all_dates = queries.get_all_race_dates()
        if not all_dates:
            print('✗ No races found')
            return False

        test_date = all_dates[0]
        courses = queries.get_courses_by_date(test_date)
        test_course = courses[0]
        races = queries.get_races(test_date, test_course)
        test_race_id = races[0]['race_id']

        print(f'✓ Found test race: {test_race_id}')
    except Exception as e:
        print(f'✗ Failed to get race: {e}')
        return False

    # Step 3: Export race entries CSV
    print()
    print('Step 3: Exporting race entries CSV...')
    try:
        csv_data = csv_export.export_race_entries_to_csv(test_race_id)
        if csv_data:
            lines = csv_data.strip().split('\n')
            print(f'✓ Exported {len(lines)-1} entries')
            print(f'  Columns: {lines[0][:100]}...')
        else:
            print('✗ No data returned')
            return False
    except Exception as e:
        print(f'✗ Export failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Export all races CSV
    print()
    print('Step 4: Exporting all races CSV...')
    try:
        csv_data = csv_export.export_all_races_to_csv()
        if csv_data:
            lines = csv_data.strip().split('\n')
            print(f'✓ Exported {len(lines)-1} races')
        else:
            print('✗ No data returned')
            return False
    except Exception as e:
        print(f'✗ Export failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Export horse metrics CSV
    print()
    print('Step 5: Exporting horse metrics CSV...')
    try:
        csv_data = csv_export.export_horse_metrics_to_csv()
        if csv_data:
            lines = csv_data.strip().split('\n')
            print(f'✓ Exported {len(lines)-1} horse metrics')
        else:
            print('✗ No data returned')
            return False
    except Exception as e:
        print(f'✗ Export failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 6: Export entry details CSV
    print()
    print('Step 6: Exporting entry details CSV...')
    try:
        csv_data = csv_export.export_entry_details_to_csv()
        if csv_data:
            lines = csv_data.strip().split('\n')
            print(f'✓ Exported {len(lines)-1} entry details')
        else:
            print('✗ No data returned')
            return False
    except Exception as e:
        print(f'✗ Export failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 7: Export training features CSV (this is slow)
    print()
    print('Step 7: Exporting training features CSV... (this may take a moment)')
    try:
        csv_data = csv_export.export_training_features_to_csv()
        if csv_data:
            lines = csv_data.strip().split('\n')
            print(f'✓ Exported {len(lines)-1} training samples with features')
        else:
            print('✗ No data returned')
            return False
    except Exception as e:
        print(f'✗ Export failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    print()
    print('=' * 60)
    print('ALL CSV EXPORT TESTS PASSED ✓')
    print('=' * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
