#!/usr/bin/env python3
"""
scripts/setup.py
One-shot database setup + initial data load.
Run ONCE after configuring .env:

    python scripts/setup.py
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.services.data_ingestion import seed_stock_universe, refresh_all_stocks


def main():
    print("═" * 60)
    print("  MarketPulse India — Database Setup")
    print("═" * 60)

    app = create_app()
    with app.app_context():
        print("\n[1/3] Creating database tables…")
        db.create_all()
        print("      ✓ Tables created.")

        print("\n[2/3] Seeding stock universe (50 stocks)…")
        seed_stock_universe()
        print("      ✓ Stock universe seeded.")

        print("\n[3/3] Fetching 1-year history for all stocks…")
        print("      (This may take 3–5 minutes — yfinance rate-limits apply)")
        refresh_all_stocks(days=365)
        print("      ✓ Initial data load complete.")

    print("\n" + "═" * 60)
    print("  Setup complete!  Run: flask run")
    print("═" * 60)


if __name__ == '__main__':
    main()
