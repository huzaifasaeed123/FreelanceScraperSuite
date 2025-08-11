#!/usr/bin/env python3
"""
Main scraper runner - executes all scrapers step by step
"""

import time
import sys
import os

# Import your scraper modules
from LocalScraper import Local_Scraper
from MoneyHouse_Scraper import moneyhouse_main
from OutpuFormatting import OutPutFormatting

def main():
    """Run all scrapers in sequence"""
    
    print("=" * 60)
    print("STARTING COMPLETE SCRAPING PROCESS")
    print("=" * 60)
    
    try:
        # Step 1: Run Local.ch Scraper
        print("\n🔄 STEP 1: Starting Local.ch Scraper...")
        print("-" * 40)
        start_time = time.time()
        
        Local_Scraper()
        
        elapsed = time.time() - start_time
        print(f"✅ Local.ch Scraper completed in {elapsed:.2f} seconds")
        
        # Small delay between scrapers
        print("⏳ Waiting 30 seconds before next scraper...")
        time.sleep(30)
        
        # Step 2: Run MoneyHouse Scraper
        print("\n🔄 STEP 2: Starting MoneyHouse Scraper...")
        print("-" * 40)
        start_time = time.time()
        
        moneyhouse_main()
        
        elapsed = time.time() - start_time
        print(f"✅ MoneyHouse Scraper completed in {elapsed:.2f} seconds")
        
        # Small delay before formatting
        print("⏳ Waiting 10 seconds before formatting...")
        time.sleep(10)
        
        # Step 3: Run Output Formatting
        print("\n🔄 STEP 3: Starting Output Formatting...")
        print("-" * 40)
        start_time = time.time()
        
        OutPutFormatting()
        
        elapsed = time.time() - start_time
        print(f"✅ Output Formatting completed in {elapsed:.2f} seconds")
        
        print("\n" + "=" * 60)
        print("🎉 ALL SCRAPING PROCESSES COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Show final output files
        print("\n📄 Generated Files:")
        print("- Final_Combined.db (Database)")
        print("- combined_large.xlsx (Complete data)")
        print("- combined_small.xlsx (Essential data)")
        print("- branche_spreadsheets_L/ (Large format by industry)")
        print("- branche_spreadsheets_S/ (Small format by industry)")
        
    except KeyboardInterrupt:
        print("\n⚠️  Process interrupted by user (Ctrl+C)")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        print("Check the error details above and try again.")
        sys.exit(1)

if __name__ == "__main__":
    # Check if database already exists
    if os.path.exists("Final_Combined.db"):
        response = input("Final_Combined.db already exists. Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Scraping cancelled.")
            sys.exit(0)
    
    main()