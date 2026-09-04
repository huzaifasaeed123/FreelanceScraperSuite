import time
from pathlib import Path
import json
import re
import os
import glob
import shutil
import importlib.util
import hashlib
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dataclasses import dataclass, asdict, field
from typing import Dict

# Set by run_parallel.py's workers to silence per-business chatter; the
# parallel runner writes its own structured progress + per-worker logs.
QUIET = False

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday")

# Pause between search variations. The client's original code used 5s ("there
# is a 2 sec wait do drop it if you feel like you need to"); with six workers
# already spacing requests out naturally, a shorter pause is enough and saves
# ~1h across the full run. Override with MAPS_INTER_SEARCH_DELAY.
INTER_SEARCH_DELAY = float(os.environ.get("MAPS_INTER_SEARCH_DELAY", "2"))

# How long to look for the opening-hours expander, and for the panel to fill
# in once clicked. Tuned against the server's latency; raise if a slower
# network starts producing partial open_hours.
HOURS_BUTTON_TIMEOUT = float(os.environ.get("MAPS_HOURS_BUTTON_TIMEOUT", "2.5"))
HOURS_EXPAND_TIMEOUT = float(os.environ.get("MAPS_HOURS_EXPAND_TIMEOUT", "5"))

# Cumulative seconds per extraction phase, for spotting which selector chain
# is burning the time. Dumped by run_parallel workers into their logs.
import collections as _collections
TIMINGS = _collections.defaultdict(float)


def log(*a, **kw):
    """Chatty progress output, suppressed when QUIET (parallel workers keep
    their own per-worker logs and the runner prints structured progress)."""
    if not QUIET:
        print(*a, **kw)


# AUTO-DETECT COUNTRY FILES
def detect_available_countries():
    countries_dir = "countries"
    if not os.path.exists(countries_dir):
        log(f"❌ Countries directory '{countries_dir}' not found!")
        return []
    country_files = glob.glob(os.path.join(countries_dir, "*.py"))
    countries = []
    for file_path in country_files:
        filename = os.path.basename(file_path)
        if filename != "__init__.py":
            country_name = filename[:-3]
            countries.append(country_name)
    return sorted(countries)

def load_country_module(country_name):
    try:
        module_path = os.path.join("countries", f"{country_name}.py")
        if not os.path.exists(module_path):
            raise FileNotFoundError(f"Country file {module_path} not found")
        spec = importlib.util.spec_from_file_location(country_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        log(f"❌ Error loading country module '{country_name}': {e}")
        return None

available_countries = detect_available_countries()


def configure_country(country_name):
    """Point this module at a country in-process.

    run_countries72.py switched countries by rewriting SELECTED_COUNTRY in
    this file's source before each run. That cannot work with concurrent
    workers - they all share the one file - so the parallel runner calls
    this instead. The module-level names below are kept in sync so existing
    code paths (and the __main__ block) behave exactly as before.
    """
    global SELECTED_COUNTRY, country_module, GOOGLE_MAPS_COUNTRY
    global get_major_cities, get_business_keywords
    global generate_search_variations, get_strategic_areas

    module = load_country_module(country_name)
    if module is None:
        raise RuntimeError(f"could not load country module: {country_name}")

    SELECTED_COUNTRY = country_name
    country_module = module
    get_major_cities = module.get_major_cities
    get_business_keywords = module.get_business_keywords
    generate_search_variations = module.generate_search_variations
    get_strategic_areas = module.get_strategic_areas
    GOOGLE_MAPS_COUNTRY = getattr(module, 'GOOGLE_MAPS_COUNTRY', country_name)
    return module


SELECTED_COUNTRY = "ghana"  # week-4 default; run_parallel.py reconfigures per country

if SELECTED_COUNTRY in available_countries:
    configure_country(SELECTED_COUNTRY)
else:
    log(f"❌ Country '{SELECTED_COUNTRY}' not found. Available: {available_countries}")
    exit(1)


@dataclass
class Selectors:
    scroll_area: str = '//div[@role="feed"]'
    business_card: str = '//a[contains(@href, "/maps/place")]'
    back_button: str = '//button[@aria-label="Back"]'
    title: str = '//h1'
    rating: str = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[contains(@class,"fontDisplayLarge")]'
    rating_alt: str = '//span[@role="img"][@aria-label]'
    rating_alt2: str = '//div[contains(@aria-label,"stars")]'
    reviews_count: str = '//div[@jsaction="pane.reviewChart.moreReviews"]//span[contains(text(),"reviews")]'
    reviews_count_alt: str = '//button[contains(@aria-label,"reviews")]'
    reviews_count_alt2: str = '//span[contains(text(),"review")]'
    # Current Maps DOM puts "4.9\n(1,572)" in the rating block; the three
    # selectors above are all legacy layouts that no longer match.
    reviews_block: str = '//div[contains(@class,"F7nice")]'
    website: str = '//a[@data-tooltip="Open website"]'
    website_alt1: str = '//a[@data-item-id="authority"]'
    website_alt2: str = '//a[contains(@aria-label,"Website")]'
    website_alt3: str = '//div[@data-attrid="kc:/location/location:website"]//a'
    website_alt4: str = '//button[contains(@aria-label,"Website")]/..//a'
    phone_number: str = '//button[@data-tooltip="Copy phone number"]'
    phone_alt1: str = '//button[contains(@aria-label,"Phone")]'
    phone_alt2: str = '//button[@data-item-id="phone:tel"]'
    phone_alt3: str = '//div[@data-attrid="kc:/location/location:phone"]//span[2]'
    phone_alt4: str = '//button[contains(@data-item-id,"phone")]'
    phone_alt5: str = '//a[contains(@href,"tel:")]'
    hours_button: str = '//span[contains(@aria-label, "Show open hours for the week")]'
    # The span above is only an icon - clicking it does nothing. The real
    # expander is its role="button" ancestor carrying the openhours jsaction.
    hours_button_alt: str = '//*[@role="button" and contains(@jsaction,"openhours")]'
    # Per-day "Copy open hours" buttons, present once expanded. Used as a
    # fallback when the table markup shifts.
    hours_aria_days: str = '//*[contains(@aria-label,"Copy open hours")]'
    hours_table: str = '//div/table[contains(@class,"fontBodyMedium")]'
    hours_table_alt: str = '//table[contains(@aria-label,"Opening hours")]'
    hours_table_alt2: str = '//table'
    hours_table_rows: str = './/tr'
    hours_table_day_cell: str = './/td[1]'
    hours_table_time_cell: str = './/td[2]'


@dataclass
class BusinessData:
    name: str = None
    website: str = None
    phone_number: str = None
    latitude: str = None
    longitude: str = None
    image: str = None
    open_hours: Dict[str, str] = field(default_factory=dict)
    rating: float = None
    reviews_count: int = None
    maps_url: str = None


def _extract_hours_from_table(driver, table, selectors):
    hours = {}
    rows = table.find_elements(By.XPATH, selectors.hours_table_rows)
    for row in rows:
        try:
            cells = row.find_elements(By.XPATH, './/td')
            # Google currently renders all 7 days inside a single <tr>, so
            # reading only cells[0]/cells[1] yields just one day (the bug the
            # client reported). Walk every cell and pair up day/time as we go.
            texts = []
            for cell in cells:
                txt = cell.text.strip()
                if not txt:
                    txt = driver.execute_script("return arguments[0].innerText;", cell).strip()
                texts.append(txt)

            pending_day = None
            for txt in texts:
                if not txt:
                    continue
                if txt in DAY_NAMES:
                    pending_day = txt
                elif pending_day:
                    hours[pending_day] = txt
                    pending_day = None
        except Exception:
            continue
    return hours


def _extract_hours_from_aria(driver, selectors):
    """Fallback: once the panel is expanded Google renders one
    'Wednesday, 10 AM to 8 PM, Copy open hours' button per day. This survives
    table markup changes, so it's a useful backstop for the table parser."""
    hours = {}
    try:
        for el in driver.find_elements(By.XPATH, selectors.hours_aria_days):
            label = el.get_attribute('aria-label') or ''
            m = re.match(r'\s*(\w+),\s*(.+?),\s*Copy open hours', label)
            if m and m.group(1) in DAY_NAMES:
                hours[m.group(1)] = m.group(2).strip()
    except Exception:
        pass
    return hours


def extract_open_hours(driver, selectors, wait):
    hours = {}
    try:
        # Click the role="button" ancestor, not the icon span - the span
        # carries the aria-label but has no click handler of its own.
        #
        # Use a short wait, not the shared 10s one: plenty of listings have no
        # hours section at all, and on those the default wait burned 10s (then
        # another 10s on the fallback selector) to learn nothing. The detail
        # pane is already loaded by this point, so if the expander isn't
        # there within a couple of seconds it isn't coming.
        short_wait = WebDriverWait(driver, HOURS_BUTTON_TIMEOUT)
        try:
            expander = short_wait.until(EC.element_to_be_clickable((By.XPATH, selectors.hours_button_alt)))
        except TimeoutException:
            expander = short_wait.until(EC.element_to_be_clickable((By.XPATH, selectors.hours_button)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", expander)
        try:
            expander.click()
        except Exception:
            driver.execute_script("arguments[0].click();", expander)

        # Poll for the expanded panel rather than sleeping a fixed 4s. The
        # per-day "Copy open hours" buttons only exist once it's open, so
        # their presence is an exact readiness signal - typically ready in
        # well under a second, vs 4s every single business before.
        #
        # Stop as soon as all 7 days are present. Waiting for the full
        # deadline on listings that expose fewer days (24h venues, temporarily
        # closed) was costing seconds per business on the server, where round
        # trips are slower than on a dev box.
        deadline = time.time() + HOURS_EXPAND_TIMEOUT
        stable_since, last_count = None, 0
        while time.time() < deadline:
            count = len(driver.find_elements(By.XPATH, selectors.hours_aria_days))
            if count >= 7:
                break
            if count != last_count:
                last_count, stable_since = count, time.time()
            elif count >= 1 and stable_since and time.time() - stable_since > 0.6:
                # Panel opened and stopped growing - this listing just has
                # fewer than 7 rows. No point waiting out the deadline.
                break
            time.sleep(0.15)

        # Try every candidate table selector and keep whichever table actually
        # yields the most day entries. A bare '//table' selector can match the
        # wrong element (e.g. a one-row "today only" summary widget instead of
        # the real 7-day table), so picking "first match" here is unreliable -
        # picking "most complete match" is not.
        best_hours = {}
        for table_selector in [selectors.hours_table, selectors.hours_table_alt, selectors.hours_table_alt2]:
            try:
                tables = driver.find_elements(By.XPATH, table_selector)
            except Exception:
                continue
            for table in tables:
                try:
                    candidate = _extract_hours_from_table(driver, table, selectors)
                except Exception:
                    continue
                if len(candidate) > len(best_hours):
                    best_hours = candidate
            if len(best_hours) >= 7:
                break

        # Backstop: per-day aria-labels. Kept whenever it beats the table
        # parse, so a future table markup change degrades instead of breaking.
        aria_hours = _extract_hours_from_aria(driver, selectors)
        hours = aria_hours if len(aria_hours) > len(best_hours) else best_hours
    except TimeoutException:
        pass
    except Exception as e:
        log(f"      ❌ Error extracting hours: {e}")
    return hours


def extract_website(driver, selectors):
    for selector in [selectors.website, selectors.website_alt1, selectors.website_alt2,
                     selectors.website_alt3, selectors.website_alt4]:
        try:
            element = driver.find_element(By.XPATH, selector)
            website = element.get_attribute('href')
            if website and website.startswith('http'):
                return website
        except NoSuchElementException:
            continue
    try:
        all_links = driver.find_elements(By.XPATH, '//a[@href]')
        for link in all_links:
            href = link.get_attribute('href')
            if href and 'http' in href and 'google' not in href and 'maps' not in href:
                parent_text = link.find_element(By.XPATH, '..').text.lower()
                if any(kw in parent_text for kw in ['website', 'site web', 'web']):
                    return href
    except Exception:
        pass
    log(f"      ⚠️ No website found")
    return None


def extract_phone_number(driver, selectors):
    phone_selectors = [
        (selectors.phone_number, 'aria-label'),
        (selectors.phone_alt1, 'aria-label'),
        (selectors.phone_alt2, 'aria-label'),
        (selectors.phone_alt3, 'text'),
        (selectors.phone_alt4, 'aria-label'),
        (selectors.phone_alt5, 'href'),
    ]
    for selector, attr_type in phone_selectors:
        try:
            element = driver.find_element(By.XPATH, selector)
            if attr_type == 'text':
                phone = element.text
            elif attr_type == 'href':
                phone = element.get_attribute('href')
                if phone and phone.startswith('tel:'):
                    phone = phone.replace('tel:', '')
            else:
                phone = element.get_attribute(attr_type)
            if phone:
                phone = re.sub(r'Phone:\s*', '', phone)
                phone = re.sub(r'Call phone number\s*', '', phone)
                phone = phone.strip()
                if phone and len(phone) >= 8:
                    return phone
        except NoSuchElementException:
            continue
    try:
        page_text = driver.find_element(By.XPATH, '//body').text
        for pattern in [
            r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}',
            r'\d{2}\s\d{2}\s\d{2}\s\d{2}\s\d{2}',
            r'\d{10}',
        ]:
            for match in re.findall(pattern, page_text):
                if len(match) >= 10 and not match.startswith('2024') and not match.startswith('2025') and not match.startswith('2026'):
                    return match
    except Exception:
        pass
    log(f"      ⚠️ No phone number found")
    return None


def parse_business_details(driver, selectors, wait, maps_url=None):
    data = BusinessData()
    data.maps_url = maps_url
    try:
        wait.until(EC.url_contains('/place/'))
        title_element = wait.until(EC.presence_of_element_located((By.XPATH, selectors.title)))
        data.name = title_element.text
        if not data.name or data.name.lower() == "results":
            time.sleep(2)
            data.name = driver.find_element(By.XPATH, selectors.title).text
    except TimeoutException:
        log("      ⚠️ Could not extract business name. Skipping.")
        return None

    for rating_selector in [selectors.rating, selectors.rating_alt, selectors.rating_alt2]:
        try:
            element = driver.find_element(By.XPATH, rating_selector)
            rating_text = element.text.strip() or element.get_attribute('aria-label')
            if rating_text:
                m = re.search(r'(\d+\.?\d*)', rating_text.replace(',', '.'))
                if m:
                    data.rating = float(m.group(1))
                    break
        except (NoSuchElementException, ValueError):
            continue

    # Primary: the rating block renders as "4.9\n(1,572)" - take the
    # parenthesised figure so the rating itself is never mistaken for a count.
    try:
        for element in driver.find_elements(By.XPATH, selectors.reviews_block):
            block_text = driver.execute_script("return arguments[0].innerText;", element) or ''
            m = re.search(r'\(([\d.,\s  ]+)\)', block_text)
            if m:
                digits = re.sub(r'[^\d]', '', m.group(1))
                if digits:
                    data.reviews_count = int(digits)
                    break
    except Exception:
        pass

    if data.reviews_count is None:
        for reviews_selector in [selectors.reviews_count, selectors.reviews_count_alt, selectors.reviews_count_alt2]:
            try:
                element = driver.find_element(By.XPATH, reviews_selector)
                reviews_text = element.text.strip() or element.get_attribute('aria-label')
                if reviews_text:
                    m = re.search(r'(\d+)', reviews_text.replace(',', '').replace(' ', ''))
                    if m:
                        data.reviews_count = int(m.group(1))
                        break
            except (NoSuchElementException, ValueError):
                continue

    # Prefer the large hero photo, but accept any reasonably sized business
    # photo. Google also serves w224 variants now, and hardcoding only
    # w256/w408 silently dropped the image on many listings. Avatars
    # (-rp-mo-/-br100 suffixes) and tiny thumbs are excluded deliberately.
    try:
        best_img, best_width = None, 0
        for img in driver.find_elements(By.XPATH, '//img[contains(@src, "googleusercontent.com")]'):
            src = img.get_attribute('src')
            if not src or 'br100' in src or '-rp-mo-' in src:
                continue
            m = re.search(r'=w(\d+)', src)
            if not m:
                continue
            width = int(m.group(1))
            if width >= 150 and width > best_width:
                best_img, best_width = src, width
        data.image = best_img
    except Exception:
        pass

    _t = time.time()
    data.website = extract_website(driver, selectors)
    TIMINGS['website'] += time.time() - _t

    _t = time.time()
    data.phone_number = extract_phone_number(driver, selectors)
    TIMINGS['phone'] += time.time() - _t

    try:
        current_url = driver.current_url
        lat_m = re.search(r'!3d([-+]?[0-9]*\.?[0-9]+)', current_url)
        lon_m = re.search(r'!4d([-+]?[0-9]*\.?[0-9]+)', current_url)
        if lat_m and lon_m:
            data.latitude = lat_m.group(1)
            data.longitude = lon_m.group(1)
        elif "@" in current_url:
            coord_m = re.search(r'@([-+]?[0-9]*\.?[0-9]+),([-+]?[0-9]*\.?[0-9]+)', current_url)
            if coord_m:
                data.latitude = coord_m.group(1)
                data.longitude = coord_m.group(2)
    except Exception:
        pass

    if data.latitude and data.longitude:
        country_code = getattr(country_module, 'COUNTRY_CODE', None)
        if country_code and not is_valid_country_location(data.latitude, data.longitude, country_code):
            log(f"      ⚠️ REJECTED: Business outside {country_code} bounds")
            return None

    _t = time.time()
    data.open_hours = extract_open_hours(driver, selectors, wait)
    TIMINGS['hours'] += time.time() - _t
    log(f"   📊 {data.name} | Website: {'✓' if data.website else '✗'} | Phone: {'✓' if data.phone_number else '✗'}")
    return data


def safe_filename(name: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9_\-]+', "_", name).lower()
    # Non-Latin keywords (Japanese, Cyrillic, Arabic, Devanagari) have no
    # characters the pattern above keeps, so they all collapsed to the same
    # slug - every keyword for a city then shared one filename and only the
    # first was ever scraped. Fall back to a hash so each keyword stays
    # distinct. Latin names are untouched, so existing checkpoints still
    # resolve and completed work is never redone.
    if slug.strip("_-") == "":
        slug = hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    return slug


def get_country_language_settings(country_code: str) -> tuple:
    language_map = {
        "LB": ("ar-LB", "ar-LB,ar,fr-LB,fr,en-US,en", "ar"),
        "JO": ("ar-JO", "ar-JO,ar,en-US,en", "ar"),
        "SY": ("ar-SY", "ar-SY,ar,en-US,en", "ar"),
        "IQ": ("ar-IQ", "ar-IQ,ar,en-US,en", "ar"),
        "PS": ("ar-PS", "ar-PS,ar,en-US,en", "ar"),
        "CA": ("en-CA", "en-CA,en,fr-CA,fr", "en"),              # Canada — English + French
    }
    return language_map.get(country_code, ("en-US", "en-US,en", "en"))


def is_valid_country_location(latitude: str, longitude: str, country_code: str) -> bool:
    try:
        lat = float(latitude)
        lon = float(longitude)
        bounds = {
            "LB": (33.0, 34.7, 35.1, 36.7),
            "JO": (29.1, 33.4, 34.9, 39.3),
            "SY": (32.3, 37.4, 35.6, 42.4),
            "IQ": (29.0, 37.4, 38.7, 48.7),
            "PS": (31.2, 32.6, 34.2, 35.6),
            "CA": (41.6, 83.1, -141.0, -52.6),  # Canada bounding box
        }
        if country_code in bounds:
            min_lat, max_lat, min_lon, max_lon = bounds[country_code]
            return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
        return True
    except (ValueError, TypeError):
        return False


def place_key(link: str) -> str:
    """Stable identity for a Maps place URL.

    The same business reached via different searches gets different @lat,lng
    zoom prefixes but keeps its '!1s0x<hex>:0x<hex>' place id, so key on that
    when available and fall back to the raw URL when it isn't.
    """
    if not link:
        return ""
    m = re.search(r'!1s(0x[0-9a-f]+:0x[0-9a-f]+)', link)
    if m:
        return m.group(1)
    m = re.search(r'/place/([^/@]+)', link)
    if m:
        return m.group(1)
    return link


def resolve_chromedriver() -> str:
    """Locate chromedriver next to this file, tolerating the Windows .exe
    suffix vs the bare Linux name, then fall back to PATH."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "chromedriver.exe", here / "chromedriver"):
        if candidate.exists():
            return str(candidate)
    found = shutil.which("chromedriver")
    if found:
        return found
    raise FileNotFoundError(
        f"chromedriver not found in {here} or on PATH. "
        "Place the binary next to googlescrap72.py."
    )


def find_search_box(driver, wait):
    try:
        return wait.until(EC.element_to_be_clickable((By.ID, "searchboxinput")))
    except TimeoutException:
        pass
    for by_method, selector in [
        (By.ID, "searchbox"),
        (By.NAME, "q"),
        (By.XPATH, "//input[@aria-label]"),
        (By.XPATH, "//input[@type='search']"),
        (By.CSS_SELECTOR, "input[name='q']"),
    ]:
        try:
            return wait.until(EC.element_to_be_clickable((by_method, selector)))
        except (TimeoutException, NoSuchElementException):
            continue
    raise NoSuchElementException("Could not find Google Maps search box")


def scrape_google_maps(search_term, max_places=10, output_file=None, all_scraped_data=None,
                       skip_links=None):
    country_code = getattr(country_module, 'COUNTRY_CODE', None)
    lang_code, accept_langs, maps_hl = get_country_language_settings(country_code)

    options = Options()
    options.add_argument("--headless=new")
    # CRITICAL: headless Chrome advertises "HeadlessChrome/..." in its UA and
    # Google serves it a stripped page - one day of opening hours instead of
    # seven, and no review count at all. Overriding the UA restores the full
    # payload while staying headless. Verified 2026-08-05: same URL, same
    # minute, 1 day -> 7 days and reviews_count null -> 1572.
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    )
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-geolocation")
    options.add_argument(f"--lang={lang_code}")
    options.add_argument(f"--accept-lang={accept_langs}")
    # Speed: Maps is fully usable without fetching photo bitmaps, and the
    # image URL still comes through in the DOM. Biggest single bandwidth win
    # when six browsers share one uplink.
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--mute-audio")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    # Each parallel worker needs its own profile dir, otherwise concurrent
    # Chromes contend for the same singleton lock and fail to launch.
    profile_dir = os.environ.get("MAPS_PROFILE_DIR")
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")

    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.managed_default_content_settings.images": 2,
        "intl.accept_languages": accept_langs
    })
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # driver.get() normally blocks until every subresource finishes loading.
    # Maps keeps fetching tiles and telemetry long after the business details
    # we need are in the DOM, so that wait was ~84% of per-business time.
    # "eager" returns at DOMContentLoaded and we rely on the explicit
    # WebDriverWait for <h1> to confirm the pane is actually ready.
    options.set_capability("pageLoadStrategy", "eager")

    driver = webdriver.Chrome(service=Service(resolve_chromedriver()), options=options)
    # Hide the automation fingerprint that survives the UA override.
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        })
    except Exception:
        pass

    # Block the map raster/vector tiles and telemetry beacons. None of the ten
    # fields we extract come from them, but they dominate the bytes Maps
    # pulls per page - and with six browsers sharing one uplink that
    # bandwidth is the real constraint. Business photo URLs still appear in
    # the DOM, so the "image" field survives this.
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": [
            "*/maps/vt/*",            # vector map tiles
            "*/maps/vt?*",
            "*.googleapis.com/maps/api/js/*",
            "*/gen_204*",             # telemetry beacons
            "*/log?format=*",
            "*doubleclick.net*",
            "*google-analytics.com*",
            "*/maps/preview/log204*",
        ]})
    except Exception:
        pass
    wait = WebDriverWait(driver, 10)
    selectors = Selectors()
    places_data = []

    try:
        combined_search = f"{search_term}, {GOOGLE_MAPS_COUNTRY}"
        log(f"🌐 Opening Google Maps...")
        # Use direct search URL to force list/feed view instead of single business page
        import urllib.parse
        encoded_query = urllib.parse.quote(combined_search)
        search_url = f"https://www.google.com/maps/search/{encoded_query}/?hl={maps_hl}"
        driver.get(search_url)
        # Wait for either the results feed or a consent interstitial, instead
        # of a flat 5s. Returns as soon as the page is actually usable.
        deadline = time.time() + 12
        while time.time() < deadline:
            if driver.find_elements(By.XPATH, selectors.scroll_area):
                break
            if '/place/' in driver.current_url:
                break
            if driver.find_elements(By.XPATH, '//button[contains(., "Accept") or contains(., "I agree") or contains(., "أوافق") or contains(., "Reject all") or contains(., "قبول الكل")]'):
                break
            time.sleep(0.3)

        # Handle Google consent/cookie page if it appears
        try:
            consent_btn = driver.find_element(By.XPATH, '//button[contains(., "Accept") or contains(., "I agree") or contains(., "أوافق") or contains(., "Reject all") or contains(., "قبول الكل")]')
            consent_btn.click()
            log("✅ Dismissed consent page")
            wait.until(EC.presence_of_element_located((By.XPATH, selectors.scroll_area)))
        except Exception:
            pass

        log(f"🔍 Searching for {combined_search} (Language: {lang_code})...")

        # Check if results feed appeared; if Google jumped to a single business, go back and retry via search box
        feed_found = False
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, selectors.scroll_area)))
            feed_found = True
        except TimeoutException:
            page_title = driver.title
            log(f"⚠️ Direct URL landed on single business: '{page_title}'. Retrying via search box...")

        if not feed_found:
            # Check if Google landed on a single business page (/place/ in URL)
            current_url = driver.current_url
            if '/place/' in current_url or '/maps/place/' in current_url:
                log(f"📍 Google returned a single business result. Scraping it directly...")
                business_info = parse_business_details(driver, selectors, wait, maps_url=current_url)
                if business_info:
                    places_data.append(business_info)
                    log(f"  ✅ Scraped single result: {business_info.name}")
                return places_data

            # Fallback: navigate to maps home and use search box
            driver.get(f"https://www.google.com/maps?hl={maps_hl}")
            time.sleep(3)
            try:
                search_box = find_search_box(driver, wait)
                search_box.clear()
                search_box.send_keys(combined_search)
                search_box.send_keys(Keys.ENTER)
                time.sleep(6)
                wait.until(EC.presence_of_element_located((By.XPATH, selectors.scroll_area)))
                feed_found = True
            except TimeoutException:
                # Last resort: if still on a single business page, scrape it
                current_url = driver.current_url
                if '/place/' in current_url or '/maps/place/' in current_url:
                    log(f"📍 Still on single business page after fallback. Scraping it directly...")
                    business_info = parse_business_details(driver, selectors, wait, maps_url=current_url)
                    if business_info:
                        places_data.append(business_info)
                        log(f"  ✅ Scraped single result: {business_info.name}")
                    return places_data
                page_title = driver.title
                log(f"⚠️ No results found for this search. Page title: '{page_title}'. Skipping.")
                return places_data

        log("\n--- Phase 1: Collecting business URLs ---")
        business_links = set()
        scroll_attempts = 0
        consecutive_no_new = 0
        last_scroll_height = 0

        while len(business_links) < max_places and scroll_attempts < 100:
            scrollable_div = driver.find_element(By.XPATH, selectors.scroll_area)
            cards = driver.find_elements(By.XPATH, selectors.business_card)
            new_found = 0
            for card in cards:
                link = card.get_attribute('href')
                if link and link not in business_links:
                    business_links.add(link)
                    new_found += 1
            log(f"Scroll {scroll_attempts+1}: +{new_found} new. Total: {len(business_links)}")
            if new_found == 0:
                consecutive_no_new += 1
                if consecutive_no_new >= 5:
                    log("No new links in 5 scrolls. Stopping.")
                    break
            else:
                consecutive_no_new = 0
            current_scroll_height = driver.execute_script("return arguments[0].scrollHeight", scrollable_div)
            if current_scroll_height == last_scroll_height and new_found == 0:
                try:
                    btn = driver.find_element(By.XPATH, "//span[contains(text(), 'Show more results')]/parent::button")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(3)
                except NoSuchElementException:
                    pass
            last_scroll_height = current_scroll_height
            prev_count = len(business_links)
            driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
            # Poll briefly for the next page of cards to render instead of
            # always paying a flat 1.5s. Google usually fills the feed in a
            # few hundred ms; this exits as soon as new cards appear.
            scroll_deadline = time.time() + 2.5
            while time.time() < scroll_deadline:
                time.sleep(0.25)
                if len(driver.find_elements(By.XPATH, selectors.business_card)) > prev_count:
                    break
            if scroll_attempts % 10 == 0:
                driver.execute_script('arguments[0].scrollBy(0, 1000)', scrollable_div)
                time.sleep(0.8)
            scroll_attempts += 1

        # Drop places already scraped by an earlier search variation for this
        # same (area, keyword) - same place, same data, so re-parsing it is
        # pure cost. Keyed on the stable place id (1s0x...) when present.
        if skip_links is not None:
            fresh = []
            for link in business_links:
                if place_key(link) not in skip_links:
                    fresh.append(link)
            skipped = len(business_links) - len(fresh)
            if skipped:
                log(f"⏭️  Skipping {skipped} already-scraped places from a previous variation")
            business_links = fresh

        business_links = list(business_links)[:max_places]

        log(f"\n--- Phase 2: Scraping {len(business_links)} businesses ---")
        for i, link in enumerate(business_links):
            if skip_links is not None:
                skip_links.add(place_key(link))
            log(f"\nScraping {i+1}/{len(business_links)}...")
            try:
                _t = time.time()
                driver.get(link)
                # No blind sleep here: the wait below already blocks until the
                # detail pane's <h1> exists, and it returns as soon as that
                # happens instead of always costing a fixed 4s per business.
                wait.until(EC.presence_of_element_located((By.XPATH, '//h1')))
                TIMINGS['pageload'] += time.time() - _t

                _t = time.time()
                business_info = parse_business_details(driver, selectors, wait, maps_url=link)
                TIMINGS['parse_total'] += time.time() - _t
                if business_info:
                    places_data.append(business_info)
                    log(f"  ✅ {business_info.name}")
            except Exception as e:
                log(f"  ❌ Error: {str(e)[:150]}")

    except Exception as e:
        log(f"❌ A critical error occurred in the main process: {e}")
        raise  # Re-raise so scrape_comprehensive_area can retry
    finally:
        # driver.quit() can hang or throw if the browser already died, which
        # over thousands of combos leaves orphaned Chromes eating RAM until
        # the box is exhausted. Fall back to killing the process tree.
        try:
            driver.quit()
        except Exception:
            pass
        try:
            proc = getattr(driver, "service", None)
            proc = getattr(proc, "process", None)
            if proc and proc.poll() is None:
                proc.kill()
        except Exception:
            pass

    # Only write the per-variation intermediate file when a caller explicitly
    # asks for one. scrape_comprehensive_area passes output_file=None and
    # keeps results in memory, so writing here just duplicated every record
    # to disk for no benefit - wasted IO on a six-worker run.
    if output_file and places_data:
        places_as_dict = [asdict(p) for p in places_data]
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(places_as_dict, f, ensure_ascii=False, indent=4)
        log(f"\n💾 Saved {len(places_data)} places to {output_file}")

    if all_scraped_data is not None:
        all_scraped_data.extend(places_data)
    return places_data


def clean_business_name(name):
    if not name:
        return ""
    cleaned = re.sub(r'[^\w\s]', '', name.lower().strip())
    return re.sub(r'\s+', ' ', cleaned)


def deduplicate_businesses(businesses):
    seen_coords = set()
    seen_names = set()
    unique = []
    for b in businesses:
        lat = b.get('latitude', '')
        lng = b.get('longitude', '')
        coord_key = f"{lat}_{lng}" if lat and lng else None
        if coord_key and coord_key in seen_coords:
            continue
        clean_name = clean_business_name(b.get('name', ''))
        if clean_name and clean_name in seen_names:
            continue
        if coord_key:
            seen_coords.add(coord_key)
        if clean_name:
            seen_names.add(clean_name)
        unique.append(b)
    log(f"✅ After deduplication: {len(unique)} unique businesses")
    return unique


def scrape_comprehensive_area(keyword, area, max_per_search=120, output_dir=None):
    log(f"\n🎯 Starting comprehensive scraping for '{keyword}' in {area}")
    all_data = []
    search_variations = generate_search_variations(keyword, area)
    log(f"📍 Generated {len(search_variations)} search variations")

    # Business URLs already scraped for this (area, keyword). The search
    # variations ("X in Y" / "X near Y") overlap heavily, and re-opening a
    # detail page we've already parsed costs a full page load for a record
    # that dedup would discard anyway. Skipping them is the single biggest
    # speed win available without reducing coverage.
    seen_links = set()

    for i, search_term in enumerate(search_variations[:10]):
        log(f"\n--- Search {i+1}/{min(len(search_variations), 10)}: {search_term} ---")

        # Retry up to 3 times on ChromeDriver crash
        for attempt in range(3):
            try:
                result = scrape_google_maps(search_term, max_places=max_per_search, output_file=None, all_scraped_data=all_data, skip_links=seen_links)
                if result:
                    log(f"✅ Found {len(result)} places for: {search_term}")
                else:
                    log(f"⚠️ No results for: {search_term}")
                break
            except Exception as e:
                if attempt < 2:
                    log(f"⚠️ Attempt {attempt+1} failed: {str(e)[:150]}")
                    log(f"🔄 Restarting Chrome and retrying in 15s...")
                    time.sleep(15)
                else:
                    log(f"❌ All 3 attempts failed for {search_term}: {str(e)[:150]}")

        time.sleep(INTER_SEARCH_DELAY)

    all_data_dict = [asdict(b) if hasattr(b, '__dict__') else b for b in all_data]
    unique_data = deduplicate_businesses(all_data_dict)

    # Save into country subfolder (or wherever the parallel runner asks)
    country_folder = str(output_dir) if output_dir else SELECTED_COUNTRY.lower().replace(' ', '_')
    os.makedirs(country_folder, exist_ok=True)
    output_file = f"{SELECTED_COUNTRY}_{safe_filename(area)}_{safe_filename(keyword)}_comprehensive.json"
    output_path = os.path.join(country_folder, output_file)
    # Always write, even when empty — an empty file is what marks this
    # (city, keyword) combo as "done, searched, found nothing" so restarts
    # skip it via the same file-existence check instead of retrying it
    # forever. Confirmed real bug 2026-07-15: prior "if unique_data:" guard
    # meant legitimate zero-result combos never got marked done.
    #
    # Write to a temp file then rename: os.replace is atomic, so the periodic
    # merged export never observes a half-written file and the "does this
    # file exist" resume check never sees a truncated combo as done.
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, output_path)
    if unique_data:
        log(f"💾 Saved {len(unique_data)} unique places to {output_path}")
    else:
        log(f"💾 Saved empty marker (no results) to {output_path}")

    return unique_data


if __name__ == "__main__":
    print(f"🍁 Google Maps Scraper - CANADA")
    print("="*60)

    areas = get_major_cities()
    all_keywords = get_business_keywords()  # full English list

    print(f"📍 Target Areas: {len(areas)} cities")
    print(f"🔍 Base Keywords: {', '.join(all_keywords)}")
    print(f"🎯 Country: {GOOGLE_MAPS_COUNTRY}")
    print("\n🚀 Using comprehensive scraping method")
    print("="*60)

    country_folder = SELECTED_COUNTRY.lower().replace(' ', '_')
    OLD_FORMAT_DIR = "Canada"
    RAN_ALREADY = "ran already"

    for area in areas:
        # Per-city keywords: French added for Quebec cities
        city_keywords = country_module.get_business_keywords(city=area)

        for keyword in city_keywords:
            output_file = f"{SELECTED_COUNTRY}_{safe_filename(area)}_{safe_filename(keyword)}_comprehensive.json"

            # 1. Check new-format comprehensive file
            if (os.path.exists(output_file)
                    or os.path.exists(os.path.join(country_folder, output_file))
                    or os.path.exists(os.path.join(RAN_ALREADY, output_file))):
                print(f"\n⏭️  SKIP (new format exists): {keyword} in {area}")
                continue

            # 2. Check old-format file from previous scraping run
            if country_module.is_already_scraped_old_format(area, keyword, OLD_FORMAT_DIR):
                print(f"\n⏭️  SKIP (old format exists): {keyword} in {area}")
                continue

            try:
                print(f"\n🎯 Starting: {keyword} in {area}")
                result = scrape_comprehensive_area(keyword, area)
                print("\n" + "="*70)
                if result:
                    print(f"✅ Done: {area} | {keyword} → {len(result)} businesses")
                    for b in result[:3]:
                        print(f"   • {b.get('name','N/A')} | {b.get('phone_number','N/A')} | ⭐{b.get('rating','N/A')}")
                else:
                    print(f"❌ No results for {keyword} in {area}")
                print("="*70)
            except Exception as e:
                print(f"❌ Error for {area} / {keyword}: {str(e)[:100]}")

            time.sleep(2)

    print(f"\n🎉 Scraping completed for CANADA!")
