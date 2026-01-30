"""
Browser Manager - Singleton UC Chrome Instance
Manages a shared undetected-chromedriver instance for all scrapers.
The browser stays open and uses separate tabs for each scraper.
"""

import time
import undetected_chromedriver as uc
from threading import Lock

class BrowserManager:
    """
    Singleton class to manage a shared Chrome browser instance.
    - Creates browser only once
    - Reuses the same browser across multiple scraper calls
    - Uses tabs for different scrapers
    - Auto-recovers if browser is closed externally
    """

    _instance = None
    _lock = Lock()

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
        self._driver = None
        self._main_window = None

    def _create_driver(self):
        """Create a new UC Chrome driver instance"""
        print("[BROWSER] Creating new Chrome instance...")

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # 🔹 Headless mode
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        try:
            self._driver = uc.Chrome(options=options)
            self._main_window = self._driver.current_window_handle
            print("[BROWSER] Chrome instance created successfully")
            return True
        except Exception as e:
            print(f"[BROWSER] Failed to create Chrome: {e}")
            self._driver = None
            return False

    def _is_browser_alive(self):
        """Check if browser is still running"""
        if self._driver is None:
            return False
        try:
            # Try to access a property - will fail if browser is closed
            _ = self._driver.current_url
            return True
        except:
            return False

    def get_driver(self):
        """
        Get the shared driver instance.
        Creates a new one if needed or if browser was closed.

        Returns:
            WebDriver instance or None if creation failed
        """
        with self._lock:
            if not self._is_browser_alive():
                print("[BROWSER] Browser not alive, creating new instance...")
                self._driver = None
                if not self._create_driver():
                    return None
            return self._driver

    def open_in_new_tab(self, url, wait_time=10):
        """
        Open a URL in a new tab and return the page source.

        Args:
            url: URL to open
            wait_time: Seconds to wait for page load

        Returns:
            tuple: (page_source, tab_handle) or (None, None) on failure
        """
        driver = self.get_driver()
        if not driver:
            return None, None

        try:
            # Open new tab
            driver.execute_script("window.open('');")

            # Switch to new tab (last one)
            driver.switch_to.window(driver.window_handles[-1])
            new_tab = driver.current_window_handle

            print(f"[BROWSER] Opening {url} in new tab...")
            driver.get(url)

            print(f"[BROWSER] Waiting {wait_time}s for content...")
            time.sleep(wait_time)

            page_source = driver.page_source
            print("[BROWSER] Page source captured")

            return page_source, new_tab

        except Exception as e:
            print(f"[BROWSER] Error opening URL: {e}")
            return None, None

    def close_tab(self, tab_handle):
        """
        Close a specific tab and switch back to main window.

        Args:
            tab_handle: Handle of the tab to close
        """
        driver = self.get_driver()
        if not driver or not tab_handle:
            return

        try:
            # Switch to the tab to close
            driver.switch_to.window(tab_handle)
            driver.close()

            # Switch back to main window or first available
            if self._main_window in driver.window_handles:
                driver.switch_to.window(self._main_window)
            elif driver.window_handles:
                driver.switch_to.window(driver.window_handles[0])
                self._main_window = driver.window_handles[0]

            print("[BROWSER] Tab closed")
        except Exception as e:
            print(f"[BROWSER] Error closing tab: {e}")

    def navigate_and_get_source(self, url, wait_time=10, scroll_down=False, scroll_wait=5):
        """
        Navigate to URL in a new tab, get page source, then close the tab.
        This is the main method scrapers should use.

        Args:
            url: URL to navigate to
            wait_time: Seconds to wait after page load
            scroll_down: Whether to scroll down the page (for lazy loading)
            scroll_wait: Seconds to wait after scrolling

        Returns:
            Page source HTML or None on failure
        """
        driver = self.get_driver()
        if not driver:
            return None

        tab_handle = None
        try:
            # Open new tab
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            tab_handle = driver.current_window_handle

            print(f"[BROWSER] Opening {url}...")
            driver.get(url)

            print(f"[BROWSER] Waiting {wait_time}s for content...")
            time.sleep(wait_time)

            # Optional scroll for lazy-loaded content
            if scroll_down:
                driver.execute_script("window.scrollTo(0, 500);")
                print(f"[BROWSER] Scrolling down, waiting {scroll_wait}s...")
                time.sleep(scroll_wait)

            page_source = driver.page_source
            print("[BROWSER] HTML captured")

            return page_source

        except Exception as e:
            print(f"[BROWSER] Error: {e}")
            # If browser died, reset the driver
            if not self._is_browser_alive():
                self._driver = None
            return None

        finally:
            # Close the tab
            if tab_handle:
                try:
                    driver.switch_to.window(tab_handle)
                    driver.close()
                    # Switch to remaining window
                    if driver.window_handles:
                        driver.switch_to.window(driver.window_handles[0])
                        self._main_window = driver.window_handles[0]
                except:
                    pass

    def shutdown(self):
        """Completely close the browser (for cleanup)"""
        with self._lock:
            if self._driver:
                try:
                    self._driver.quit()
                    print("[BROWSER] Chrome instance closed")
                except:
                    pass
                self._driver = None
                self._main_window = None


# Global instance - scrapers can import and use this directly
browser_manager = BrowserManager()
