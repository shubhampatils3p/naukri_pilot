import time
from typing import List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import NaukriConfig

class NaukriBot:
    def __init__(self, config: NaukriConfig, headless: bool = False):
        self.config = config
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )
        self.wait = WebDriverWait(self.driver, 20)

    def login(self):
        self.driver.get("https://www.naukri.com/")

        # 1) Click the Login button on home page
        login_btn = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[@id='login_Layer'] | //a[contains(@href,'login')]")
            )
        )
        login_btn.click()

        # 2) Wait for popup form
        # Use placeholder because there is no id/name in your HTML snippet
        email_input = self.wait.until(
            EC.visibility_of_element_located((
                By.XPATH,
                "//input[@type='text' and contains(@placeholder,'Enter your active Email ID')]"
            ))
        )
        password_input = self.wait.until(
            EC.visibility_of_element_located((
                By.XPATH,
                "//input[@type='password' and contains(@placeholder,'Enter your password')]"
            ))
        )

        # 3) Fill credentials
        email_input.clear()
        email_input.send_keys(self.config.email)
        password_input.clear()
        password_input.send_keys(self.config.password)

        # 4) Click the Login button in popup
        login_button = self.wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "button.btn-primary.loginButton"
            ))
        )
        login_button.click()

        # 5) Wait for URL to change / some generic element instead of specific id
        # Just wait until we're no longer on the popup
        self.wait.until(lambda d: "naukri.com" in d.current_url)
        print("Logged in (popup closed)")

    def search_jobs(self):
        base = "https://www.naukri.com"
        keyword_slug = "-".join(self.config.keyword.split()).lower()
        location_slug = "-".join(self.config.location.split()).lower()
        search_url = f"{base}/{keyword_slug}-jobs-in-{location_slug}"

        print(f"Opening search URL: {search_url}")
        self.driver.get(search_url)

        # Wait only for body to appear
        self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("Search page loaded (not strictly waiting for cards)")

    def get_job_cards(self):
        cards = self.driver.find_elements(
            By.CSS_SELECTOR,
            "div[data-job-id]"
        )
        print(f"get_job_cards: found {len(cards)} cards with data-job-id")
        return cards

    def apply_to_jobs(self):
        applied = 0

        import time
        time.sleep(3)

        cards = self.get_job_cards()
        if not cards:
            print("No job cards detected, stopping apply step")
            return applied

        print(f"Found {len(cards)} cards")

        for idx in range(len(cards)):
            if applied >= self.config.max_jobs:
                break

            try:
                # Always ensure we are on the main search tab before using cards
                self.driver.switch_to.window(self.driver.window_handles[0])

                # Re-fetch cards on the page (DOM may have changed)
                cards = self.get_job_cards()
                if idx >= len(cards):
                    print(f"[{idx}] Card index out of range after refresh, stopping loop")
                    break

                card = cards[idx]

                # 1) Open job details
                job_link = card.find_element(By.CSS_SELECTOR, "a.title")
                title_text = job_link.text.strip()
                print(f"[{idx}] Opening job: {title_text}")
                self.driver.execute_script("arguments[0].click();", job_link)
                time.sleep(3)

                # 2) Switch to new tab if opened
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                # 3) Find apply button
                apply_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//a[contains(., 'Apply') or contains(., 'APPLY') or contains(., 'Apply now')] | //button[contains(., 'Apply')]"
                )
                if not apply_buttons:
                    print(f"[{idx}] No apply button, skipping")
                    self._close_extra_tab()
                    continue

                apply_buttons[0].click()
                time.sleep(4)

                # 4) Detect complex forms
                extra_fields = self.driver.find_elements(
                    By.XPATH,
                    "//input[@type='text' or @type='number' or @type='email']"
                )
                dropdowns = self.driver.find_elements(By.TAG_NAME, "select")

                if len(extra_fields) > 3 or len(dropdowns) > 0:
                    print(f"[{idx}] Complex form detected for '{title_text}', skipping for tonight")
                else:
                    print(f"[{idx}] Applied (simple apply) for '{title_text}'")
                    applied += 1

                self._close_extra_tab()
            except Exception as e:
                print(f"[{idx}] Error on card: {e}")
                self._close_extra_tab()

        print(f"Applied to {applied} jobs out of requested {self.config.max_jobs}")
        return applied

    def _close_extra_tab(self):
        # Always go back to main search tab
        while len(self.driver.window_handles) > 1:
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

    def quit(self):
        self.driver.quit()