# Template for a new scraping target - country, region, or any city/keyword set.
#
# Copy this file to <name>.py in this same folder (the filename becomes the
# --countries value and the output subfolder name, e.g. copy to "germany.py"
# to scrape as "germany"). run_parallel.py auto-detects every *.py file here
# (except this template) if you don't pass --countries explicitly.
#
# Despite the "country" naming throughout this engine (a holdover from how
# it was first built), nothing requires this to actually be a country - a
# single city split into neighbourhoods, a US state's metro areas, or any
# other city/keyword list works exactly the same way. Name the file and
# COUNTRY_NAME whatever fits your target.

CITIES = [
    "City or Neighbourhood One",
    "City or Neighbourhood Two",
    # ... one entry per (city, keyword) unit you want swept. Every entry
    # here is multiplied by every keyword in BUSINESS_KEYWORDS below, so
    # 20 cities x 10 keywords = 200 combos. Each combo is one independent,
    # checkpointed, resumable unit of work.
]

BUSINESS_KEYWORDS = [
    "restaurant",
    "coffee shop",
    # Non-Latin keywords (Japanese, Arabic, Hindi, Cyrillic, ...) work fine -
    # googlescrap72.py's safe_filename() hashes them into a unique filename
    # instead of collapsing every non-Latin keyword in a city to the same
    # file (a real bug that silently dropped ~95% of a batch before the fix -
    # see the "Non-Latin keyword filenames" section in DEPLOYMENT.md before
    # touching safe_filename()).
]


def get_major_cities():
    return CITIES


def get_business_keywords(city=None):
    # city is passed in case a real job wants different keywords per city -
    # return BUSINESS_KEYWORDS unchanged unless you need that.
    return BUSINESS_KEYWORDS


def is_already_scraped_old_format(city, keyword, old_format_dir=None):
    # Legacy-format resume check, from before per-combo checkpoint files
    # existed. New jobs have no legacy data to check against - always False.
    # Resume-safety comes entirely from googlescrap72.py's own file-existence
    # check (output/<name>/<name>_<city>_<keyword>_comprehensive.json), not
    # from this function.
    return False


def generate_search_variations(keyword, area):
    # Each variation is tried and results merged/deduped - more variations
    # means more coverage per combo but more page loads (time). Three is the
    # proven default; drop to one for a faster/shallower pass.
    return [
        f"{keyword} in {area}",
        f"{keyword} near {area}",
        f"{keyword} {area}",
    ]


def get_strategic_areas():
    return []


COUNTRY_NAME = "Template"
COUNTRY_CODE = "XX"  # documentation only, not wired into any bounds/language map
GOOGLE_MAPS_COUNTRY = "Template"
