#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Local data pipeline test
Tests: database init, data generation, ETL, and model training
"""

import sys
import os
from pathlib import Path

# Set up path
project_root = Path.cwd()
sys.path.insert(0, str(project_root))

# Fix for Windows console encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print('=' * 60)
    print('LOCAL DATA PIPELINE TEST')
    print('=' * 60)
    print(f'Working directory: {project_root}')
    print()

    # Step 1: Initialize database
    print('Step 1: Initializing database...')
    try:
        from app import db

        # Remove old database to start fresh
        db_path = project_root / 'data' / 'keiba.db'
        if db_path.exists():
            db_path.unlink()
            print('  Removed old database')

        conn = db.get_connection()
        cursor = conn.cursor()

        # Read and execute schema
        schema_path = project_root / 'sql' / 'schema.sql'
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        cursor.executescript(schema_sql)
        conn.commit()
        conn.close()
        print('✓ Database initialized')
    except Exception as e:
        print(f'✗ Database init failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Generate test data
    print()
    print('Step 2: Generating test data (1 year)...')
    try:
        from app import test_data

        races = test_data.generate_test_races(years=1)
        horses = test_data.generate_test_horses(count=150)
        jockeys = test_data.generate_test_jockeys(count=40)
        trainers = test_data.generate_test_trainers(count=40)
        entries = test_data.generate_test_entries(races, horses, jockeys, trainers)

        print(f'✓ Generated {len(races)} races')
        print(f'✓ Generated {len(horses)} horses')
        print(f'✓ Generated {len(entries)} entries')

        # Check finish_pos distribution
        finish_positions = [e['finish_pos'] for e in entries if e['finish_pos'] is not None]
        print(f'✓ Entries with results (finish_pos != None): {len(finish_positions)}')

    except Exception as e:
        print(f'✗ Test data generation failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 3: Run ETL
    print()
    print('Step 3: Running ETL pipeline...')
    try:
        from etl import upsert_master, upsert_race, upsert_entry

        print('  - Upserting horses...')
        upsert_master.MasterDataUpsert().upsert_horses(horses)

        print('  - Upserting jockeys...')
        upsert_master.MasterDataUpsert().upsert_jockeys(jockeys)

        print('  - Upserting trainers...')
        upsert_master.MasterDataUpsert().upsert_trainers(trainers)

        print('  - Upserting races...')
        upsert_race.RaceUpsert().upsert_races(races)

        print('  - Upserting entries...')
        upsert_entry.EntryUpsert().upsert_entries(entries)

        print('  - Building metrics...')
        from metrics import build_horse_metrics
        build_horse_metrics.build_all_horse_metrics(incremental=False)

        print('✓ ETL complete')

    except Exception as e:
        print(f'✗ ETL failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Check training data
    print()
    print('Step 4: Checking training data availability...')
    try:
        from app import db
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN finish_pos IS NOT NULL THEN 1 ELSE 0 END) as with_results
            FROM race_entries
        ''')
        total, with_results = cursor.fetchone()
        print(f'✓ Total entries: {total}')
        print(f'✓ Entries with results: {with_results}')

        # Check if sufficient for TimeSeriesSplit
        if with_results >= 50:
            print('✓ SUFFICIENT data for TimeSeriesSplit (3 splits)')
        else:
            print(f'✗ INSUFFICIENT data: {with_results} < 50 required')
            return False

        conn.close()

    except Exception as e:
        print(f'✗ Training data check failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Test prediction model training
    print()
    print('Step 5: Testing LightGBM model training...')
    try:
        from app import prediction_model_lightgbm as pml

        model = pml.AdvancedRacePredictionModel()
        print(f'✓ Model initialized ({model.model_name})')

        if not model.is_trained:
            print('  Training model with TimeSeriesSplit...')
            cv_results = model.train_with_cross_validation()
            print(f'✓ Model trained')
            print(f'  - Mean CV accuracy: {cv_results["mean_cv_accuracy"]:.4f}')
            print(f'  - Std CV accuracy: {cv_results["std_cv_accuracy"]:.4f}')
            print(f'  - Fold scores: {[f"{s:.4f}" for s in cv_results["cv_scores"]]}')
        else:
            print('✓ Model already trained')

    except Exception as e:
        print(f'✗ Model training failed: {e}')
        import traceback
        traceback.print_exc()
        return False

    print()
    print('=' * 60)
    print('ALL TESTS PASSED ✓')
    print('=' * 60)
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
