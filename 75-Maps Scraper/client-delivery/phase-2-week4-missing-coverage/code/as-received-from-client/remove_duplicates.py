#!/usr/bin/env python3
"""
Remove cities from week_4 that are already covered by big_city_pass.

Big City Pass coverage:
- India: Mumbai (10 areas) + Delhi (10 areas)
- Japan: Tokyo (12 districts) + Osaka (10 districts)

Week 4 targets many neighborhoods — need to remove the ones already done.
"""

import re
from pathlib import Path

BIG_CITY_PASS_COVERAGE = {
    'india': {
        'cities': ['Mumbai', 'Delhi'],
        'areas': [
            # Mumbai districts
            'South Mumbai', 'Bandra', 'Andheri', 'Juhu', 'Powai',
            'Dadar', 'Malad', 'Borivali', 'Thane', 'Navi Mumbai',
            # Delhi areas
            'Connaught Place', 'South Delhi', 'North Delhi', 'Dwarka',
            'Rohini', 'Saket', 'Karol Bagh', 'Lajpat Nagar',
            'Vasant Kunj', 'Gurgaon',
        ]
    },
    'japan': {
        'cities': ['Tokyo', 'Osaka'],
        'areas': [
            # Tokyo wards
            'Shinjuku', 'Shibuya', 'Minato', 'Chiyoda', 'Chuo',
            'Setagaya', 'Nakano', 'Toshima', 'Bunkyo', 'Taito',
            'Sumida', 'Koto',
            # Osaka wards
            'Kita', 'Naniwa', 'Tennoji', 'Nishi', 'Yodogawa',
            'Abeno', 'Sumiyoshi', 'Higashinari', 'Fukushima',
            # Note: 'Chuo' appears in both Tokyo and Osaka, but context matters
            # 'Minato' appears in both, same issue
            # We'll be conservative and remove both
        ]
    }
}

def normalize_area(area):
    """Normalize area name for comparison."""
    return area.strip().lower()

def should_remove(city_name):
    """Check if city should be removed (already covered by big_city_pass)."""
    city_norm = normalize_area(city_name)

    # Check India overlaps
    for area in BIG_CITY_PASS_COVERAGE['india']['areas']:
        if normalize_area(area) == city_norm:
            return True, 'india', area

    # Check Japan overlaps
    for area in BIG_CITY_PASS_COVERAGE['japan']['areas']:
        if normalize_area(area) == city_norm:
            return True, 'japan', area

    return False, None, None

def process_country_file(country_name, filepath):
    """Process and clean a country file."""
    print(f"\n{'='*60}")
    print(f"Processing: {country_name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"File not found: {filepath}")
        return

    with open(filepath) as f:
        content = f.read()

    # Parse MISSING_CITIES list
    match = re.search(r'MISSING_CITIES = \[(.*?)\]', content, re.DOTALL)
    if not match:
        print("Could not find MISSING_CITIES list")
        return

    cities_section = match.group(1)
    cities = re.findall(r'"([^"]+)"', cities_section)

    print(f"Total cities in week_4: {len(cities)}")

    # Find duplicates
    duplicates = []
    for city in cities:
        should_remove_city, source_country, matched_area = should_remove(city)
        if should_remove_city:
            duplicates.append((city, source_country, matched_area))

    print(f"Duplicates found (already in big_city_pass): {len(duplicates)}")

    if duplicates:
        print("\nDuplicates:")
        for city, src_country, matched in duplicates:
            print(f"  - {city:<30} (matches big_city_pass {src_country}: {matched})")

    # Create cleaned version
    new_cities = [c for c in cities if not should_remove(c)[0]]

    print(f"\nAfter removal: {len(new_cities)} cities")
    print(f"Removed: {len(cities) - len(new_cities)} cities")

    if len(new_cities) == len(cities):
        print("✓ No changes needed")
        return

    # Reconstruct file
    new_cities_str = ',\n    '.join([f'"{city}"' for city in new_cities])
    new_content = re.sub(
        r'MISSING_CITIES = \[.*?\]',
        f'MISSING_CITIES = [\n    {new_cities_str},\n]',
        content,
        flags=re.DOTALL
    )

    # Save backup
    backup_path = filepath.with_suffix('.py.bak')
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"✓ Backup saved to: {backup_path}")

    # Save updated file
    with open(filepath, 'w') as f:
        f.write(new_content)
    print(f"✓ Updated file saved to: {filepath}")

# Main
if __name__ == '__main__':
    countries_dir = Path(__file__).parent / 'countries'

    # Process India and Japan (they have overlaps)
    for country in ['india', 'japan']:
        country_file = countries_dir / f'{country}.py'
        process_country_file(country, country_file)

    # Check other countries (no overlaps expected)
    other_countries = ['bahrain', 'ghana', 'south_africa', 'uruguay']
    print(f"\n{'='*60}")
    print("Other countries (no big_city_pass overlap expected):")
    print(f"{'='*60}")
    for country in other_countries:
        filepath = countries_dir / f'{country}.py'
        if filepath.exists():
            with open(filepath) as f:
                cities_match = re.search(r'MISSING_CITIES = \[(.*?)\]', f.read(), re.DOTALL)
                if cities_match:
                    cities = re.findall(r'"([^"]+)"', cities_match.group(1))
                    print(f"  {country:<15} {len(cities)} cities (no changes needed)")
        else:
            print(f"  {country:<15} FILE NOT FOUND")

    print(f"\n{'='*60}")
    print("✓ Duplicate removal complete")
    print("  Backups saved as .bak files")
    print("  Ready to run: python3 run_countries72.py")
    print(f"{'='*60}")
