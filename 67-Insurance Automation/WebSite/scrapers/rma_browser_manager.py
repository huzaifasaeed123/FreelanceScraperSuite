"""
RMA Browser Manager - Single browser instance with request queue
Handles browser lifecycle and sequential request processing
"""

import threading
import queue
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RMABrowserManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._browser = None
        self._page = None
        self._browser_lock = threading.Lock()

        # Request queue
        self._request_queue = queue.Queue()
        self._worker_thread = None
        self._running = False

        # Browser config
        self._browser_config = {
            "headless": True,
            "humanize": True,
            "os": "windows",
            "geoip": True
        }

        logger.info("RMA Browser Manager initialized")

    def start(self):
        """Start the queue worker thread"""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self._worker_thread.start()
        logger.info("RMA queue worker started")

    def stop(self):
        """Stop the worker and close browser"""
        self._running = False
        if self._worker_thread:
            self._request_queue.put(None)  # Signal to stop
            self._worker_thread.join(timeout=5)

        self._close_browser()
        logger.info("RMA Browser Manager stopped")

    def _create_browser(self):
        """Create browser if not exists"""
        if self._browser is not None:
            return True

        try:
            from camoufox.sync_api import Camoufox
            self._browser = Camoufox(**self._browser_config).__enter__()
            logger.info("RMA browser created")
            return True
        except Exception as e:
            logger.error(f"Failed to create browser: {e}")
            self._browser = None
            return False

    def _close_browser(self):
        """Close browser if open"""
        with self._browser_lock:
            if self._browser:
                try:
                    self._browser.__exit__(None, None, None)
                except:
                    pass
                self._browser = None
                self._page = None
                logger.info("RMA browser closed")

    def _process_queue(self):
        """Worker thread that processes requests one by one"""
        while self._running:
            try:
                item = self._request_queue.get(timeout=1)

                if item is None:
                    break

                params, result_holder, done_event = item

                try:
                    with self._browser_lock:
                        result = self._execute_scrape(params)
                        result_holder['result'] = result
                except Exception as e:
                    logger.error(f"Scrape error: {e}")
                    result_holder['result'] = {
                        "success": False,
                        "error": str(e),
                        "annual": [],
                        "semi_annual": []
                    }
                finally:
                    done_event.set()
                    self._request_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Queue worker error: {e}")

    def _execute_scrape(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual scraping (called within browser lock)"""
        from .rma_scraper import (
            FUEL_TYPE_MAPPING, random_sleep, fill_text_input, fill_mui_dropdown
        )

        # Ensure browser exists
        if not self._create_browser():
            return {
                "success": False,
                "error": "Failed to create browser",
                "annual": [],
                "semi_annual": []
            }

        captured_responses = []

        def capture_response(response):
            try:
                if "/offer/api/offers" in response.url and response.status == 200:
                    try:
                        response_json = response.json()
                        captured_responses.append(response_json)
                    except:
                        pass
            except:
                pass

        try:
            page = self._browser.new_page()
            page.on("response", capture_response)

            # Get mapped values (already mapped by FieldMapper)
            fuel_code = params.get('carburant', 'diesel').lower()
            fuel_display = FUEL_TYPE_MAPPING.get(fuel_code, 'DIESEL')
            plate_display = "Plaque standard"  # Always standard
            immatriculation = params.get('immatriculation', '')

            # Navigate
            page.goto("https://direct.rmaassurance.com/souscrire", timeout=60000)
            random_sleep(1000, 2000)

            # Step 1
            page.locator("button:has-text('Suivant')").first.click()
            random_sleep(1000, 2000)

            name_input = page.locator('input[name="subscriber.lastName"]')
            name_input.wait_for(state="visible", timeout=20000)
            random_sleep(1000, 2000)

            # Fill personal info
            fill_text_input(page, 'input[name="subscriber.lastName"]', params['nom'], "Last Name")
            fill_text_input(page, 'input[name="subscriber.firstName"]', params['prenom'], "First Name")
            fill_mui_dropdown(page, "Ville", params.get('ville', 'CASABLANCA'), "City")
            fill_text_input(page, 'input[name="subscriber.phone"]', params['telephone'], "Phone")

            # Format dates
            birth_date = params.get('date_naissance', '')
            if birth_date and len(birth_date) == 10:
                birth_date_formatted = f"{birth_date[8:10]}/{birth_date[5:7]}/{birth_date[0:4]}"
            else:
                birth_date_formatted = birth_date

            license_date = params.get('date_permis', '')
            if license_date and len(license_date) == 10:
                license_date_formatted = f"{license_date[8:10]}/{license_date[5:7]}/{license_date[0:4]}"
            else:
                license_date_formatted = license_date

            fill_text_input(page, 'input[placeholder="JJ/MM/AAAA"]', birth_date_formatted, "Birth Date", index=0)
            fill_text_input(page, 'input[placeholder="JJ/MM/AAAA"]', license_date_formatted, "License Date", index=1)

            # Scroll to vehicle section
            page.mouse.wheel(0, 600)
            random_sleep(1000, 1500)

            # Fill vehicle info
            fill_mui_dropdown(page, "Type de plaque", plate_display, "Plate Type")
            fill_text_input(page, 'input[name="vehicleInformations.plateNumber"]', immatriculation, "Registration")
            fill_mui_dropdown(page, "Puissance fiscale", str(params['puissance_fiscale']), "Fiscal Power")
            fill_mui_dropdown(page, "Combustible", fuel_display, "Fuel Type")

            mec_date = params.get('date_mec', '')
            if mec_date and len(mec_date) == 10:
                mec_date_formatted = f"{mec_date[8:10]}/{mec_date[5:7]}/{mec_date[0:4]}"
            else:
                mec_date_formatted = mec_date

            fill_text_input(page, 'input[placeholder="JJ/MM/AAAA"]', mec_date_formatted, "Vehicle Date", index=2)
            fill_text_input(page, 'input[name="vehicleInformations.newPrice"]', params['valeur_neuf'], "New Value")
            fill_text_input(page, 'input[name="vehicleInformations.marketPrice"]', params['valeur_actuelle'], "Market Value")
            fill_text_input(page, 'input[name="vehicleInformations.placesNumber"]', params['nombre_places'], "Number of Seats")

            # Submit
            annual_response = None
            semi_annual_response = None

            with page.expect_response(lambda r: "/offer/api/offers" in r.url and r.status == 200, timeout=30000) as resp_promise:
                page.locator("button:has-text('Suivant')").last.click()
                random_sleep(2000, 3000)

            response = resp_promise.value
            annual_response = response.json()
            random_sleep(1000, 1500)

            # Click 6 months
            try:
                six_months_label = page.locator("label[for='6 mois']")
                six_months_label.wait_for(state="visible", timeout=20000)

                with page.expect_response(
                    lambda r: "/offer/api/offers" in r.url and r.status == 200,
                    timeout=20000
                ) as response_promise:
                    six_months_label.click()
                    random_sleep(2000, 2500)

                response_6m = response_promise.value
                semi_annual_response = response_6m.json()

            except Exception as e:
                logger.warning(f"6-month capture failed: {e}")
                semi_annual_response = None

            # Process responses
            try:
                if captured_responses and len(captured_responses) > 0:
                    annual_data = captured_responses[0]
                    if isinstance(annual_data, dict) and "offers" in annual_data:
                        annual_response = annual_data["offers"]
            except:
                pass

            try:
                if captured_responses and len(captured_responses) > 1:
                    semi_annual_data = captured_responses[1]
                    if isinstance(semi_annual_data, dict) and "offers" in semi_annual_data:
                        semi_annual_response = semi_annual_data["offers"]
            except:
                pass

            page.close()

            return {
                "success": annual_response is not None,
                "annual": annual_response or [],
                "semi_annual": semi_annual_response or []
            }

        except Exception as e:
            logger.error(f"Scrape execution error: {e}")
            # On error, close browser to get fresh one next time
            self._close_browser()
            return {
                "success": False,
                "error": str(e),
                "annual": [],
                "semi_annual": []
            }

    def scrape(self, params: Dict[str, Any], timeout: int = 120) -> Dict[str, Any]:
        """
        Add scrape request to queue and wait for result

        Args:
            params: Scraping parameters
            timeout: Max wait time in seconds

        Returns:
            Scraping result
        """
        # Start worker if not running
        if not self._running:
            self.start()

        # Create result holder and event
        result_holder = {'result': None}
        done_event = threading.Event()

        # Add to queue
        self._request_queue.put((params, result_holder, done_event))
        logger.info(f"Request queued. Queue size: {self._request_queue.qsize()}")

        # Wait for result
        if done_event.wait(timeout=timeout):
            return result_holder['result']
        else:
            return {
                "success": False,
                "error": "Request timeout",
                "annual": [],
                "semi_annual": []
            }


# Global manager instance
_manager = None


def get_rma_manager() -> RMABrowserManager:
    """Get the global RMA browser manager instance"""
    global _manager
    if _manager is None:
        _manager = RMABrowserManager()
    return _manager


def scrape_rma_queued(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrape RMA using the browser manager with queue

    This is the main function to call from the website.
    It uses a single browser instance and processes requests one by one.
    """
    from .rma_scraper import filter_rma_response
    from .field_mapper import FieldMapper

    # Map form data to RMA params (handles dummy phone, plate, etc.)
    rma_params = FieldMapper.map_to_rma(params)

    # Validate required parameters after mapping
    required_fields = ['nom', 'prenom', 'carburant', 'puissance_fiscale', 'date_mec',
                      'valeur_neuf', 'valeur_actuelle', 'nombre_places',
                      'date_naissance', 'telephone']

    missing_fields = [f for f in required_fields if f not in rma_params or not rma_params[f]]
    if missing_fields:
        return {
            "success": False,
            "error": f"Missing required fields: {', '.join(missing_fields)}",
            "annual": [],
            "semi_annual": []
        }

    manager = get_rma_manager()
    result = manager.scrape(rma_params)

    # Apply filter to return only needed data
    return filter_rma_response(result)


def shutdown_rma_manager():
    """Shutdown the browser manager (call on app shutdown)"""
    global _manager
    if _manager:
        _manager.stop()
        _manager = None
