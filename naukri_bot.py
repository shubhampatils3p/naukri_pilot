import time
from typing import List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from config import NaukriConfig
from questions_ans import QUESTION_ANSWERS

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
        time.sleep(3)
        
        base = "https://www.naukri.com"
        keyword_slug = "-".join(self.config.keyword.split()).lower()
        location_slug = "-".join(self.config.location.split()).lower()
        search_url = f"{base}/{keyword_slug}-jobs-in-{location_slug}"

        print(f"Opening search URL: {search_url}")
        print("Before URL:", search_url)
        self.driver.get(search_url)

        print("After URL:", self.driver.current_url)
        print("Page Title:", self.driver.title)
        # Wait for body
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Search page loaded (not strictly waiting for cards)")

        # Try to locate the search keyword box on the results page
        try:
            # Many Naukri result pages still expose these IDs on the search bar
            key_input = self.wait.until(
                EC.visibility_of_element_located((By.ID, "qsb-keyskill-sugg"))
            )
            loc_input = self.driver.find_element(By.ID, "qsb-location-sugg")

            key_input.clear()
            key_input.send_keys(self.config.keyword)
            loc_input.clear()
            loc_input.send_keys(self.config.location)
            loc_input.send_keys(Keys.RETURN)
            print("Triggered search via search bar")
        except Exception:
            print("Search bar not found or not clickable, relying on URL filters only")

    def get_job_cards(self):
        # Use the wrapper class you pasted earlier
        cards = self.driver.find_elements(
            By.CSS_SELECTOR,
            "div.srp-jobtuple-wrapper"
        )
        print(f"get_job_cards: found {len(cards)} cards with srp-jobtuple-wrapper")
        return cards

    def apply_to_jobs(self):
        applied = 0
        results = []

        time.sleep(2)

        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.srp-jobtuple-wrapper")
                )
            )
            print("Job tuple wrappers detected by explicit wait")
        except Exception:
            print("Explicit wait for job tuple wrappers timed out, trying to read cards anyway")

        cards = self.get_job_cards()
        if not cards:
            print("No job cards detected even after wait, stopping apply step")
            return {
                "applied": 0,
                "skipped": 0,
                "details": results,
            }

        print(f"Found {len(cards)} cards")

        for idx, card in enumerate(cards):
            if applied >= self.config.max_jobs:
                break

            try:
                if len(self.driver.window_handles) > 0:
                    self.driver.switch_to.window(self.driver.window_handles[0])

                job_link = card.find_element(By.CSS_SELECTOR, "a.title")
                try:
                    title_text = (job_link.text or "").strip()
                except Exception:
                    title_text = ""
                title_text = title_text or "(no title)"
                print(f"[{idx}] Opening job: {title_text}")
                self.driver.execute_script("arguments[0].click();", job_link)
                time.sleep(3)

                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                apply_buttons = self.driver.find_elements(
                    By.XPATH,
                    "//a[contains(., 'Apply') or contains(., 'APPLY') or contains(., 'Apply now')]"
                    " | //button[contains(., 'Apply')]"
                )

                if not apply_buttons:
                    print(f"[{idx}] No apply button, skipping")
                    results.append({
                        "title": title_text,
                        "status": "skipped",
                        "reason": "No apply button",
                    })
                    self._close_extra_tab()
                    continue

                apply_buttons[0].click()
                time.sleep(4)

                # 4A) Try chatbot-style popup first
                success_chat, reason_chat = self._handle_chatbot_question(title_text)
                if success_chat:
                    print(f"[{idx}] Applied via chatbot for '{title_text}'")
                    applied += 1
                    results.append({
                        "title": title_text,
                        "status": "applied",
                        "reason": "",
                    })
                    self._close_extra_tab()
                    continue
                elif reason_chat not in ("Chatbot not visible", "No chatbot question found"):
                    # chatbot was visible but failed – treat as skipped with reason
                    print(f"[{idx}] Skipping due to chatbot issue: {reason_chat}")
                    results.append({
                        "title": title_text,
                        "status": "skipped",
                        "reason": reason_chat,
                    })
                    self._close_extra_tab()
                    continue

                # 4B) Fallback to old extra_fields/dropdowns detection
                extra_fields = self.driver.find_elements(
                    By.XPATH,
                    "//input[@type='text' or @type='number' or @type='email']"
                )
                dropdowns = self.driver.find_elements(By.TAG_NAME, "select")

                if len(extra_fields) > 3 or len(dropdowns) > 0:
                    print(f"[{idx}] Complex form detected for '{title_text}', skipping for now")
                    results.append({
                        "title": title_text,
                        "status": "skipped",
                        "reason": "Complex form (non-chatbot)",
                    })
                else:
                    print(f"[{idx}] Applied (simple apply) for '{title_text}'")
                    applied += 1
                    results.append({
                        "title": title_text,
                        "status": "applied",
                        "reason": "",
                    })

                self._close_extra_tab()

            except Exception as e:
                print(f"[{idx}] Problematic job, skipping. Error: {e}")
                results.append({
                    "title": title_text if 'title_text' in locals() else "(unknown)",
                    "status": "skipped",
                    "reason": "Error during apply flow",
                })
                try:
                    self._close_extra_tab()
                except Exception:
                    pass

        print(f"Applied to {applied} jobs out of requested {self.config.max_jobs}")
        skipped = len([r for r in results if r["status"] == "skipped"])
        return {
            "applied": applied,
            "skipped": skipped,
            "details": results,
        }
    
    def _close_extra_tab(self):
        try:
            # Always go back to main search tab
            while len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception as e:
            print(f"_close_extra_tab: error while closing tabs: {e}")

    def quit(self):
        self.driver.quit()

    def _handle_chatbot_question(self, title_text: str):
        try:
            container = self.driver.find_element(
                By.CSS_SELECTOR, "div.chatbot_DrawerContentWrapper"
            )

            question_spans = container.find_elements(
                By.CSS_SELECTOR, "div.chatbot_MessageContainer li.botItem.chatbot_ListItem div.botMsg span"
            )
            if not question_spans:
                return False, "No chatbot question found"

            question_text = question_spans[-1].text.strip()
            print(f"Chatbot question for '{title_text}': {question_text!r}")

            answer = self._get_answer_for_chatbot_question(question_text)
            print(f"Answering chatbot with: {answer!r}")

            # contenteditable input
            input_div = container.find_element(
                By.CSS_SELECTOR,
                "div.textArea[contenteditable='true'][data-placeholder='Type message here...']"
            )
            
            actions = ActionChains(self.driver)
            actions.move_to_element(input_div).click().perform()
            input_div.send_keys(answer)

            # CLICK THE SAVE DIV, not a button
            save_div = container.find_element(
                By.CSS_SELECTOR,
                "div.sendMsgbtn_container div.sendMsg"
            )
            actions.move_to_element(save_div).click().perform()
            # or: save_div.click()
            time.sleep(2)

            return True, ""
        except Exception as e:
            print(f"_handle_chatbot_question error for '{title_text}': {e}")
            return False, "Error handling chatbot question"

    def _get_answer_for_chatbot_question(self, question_text: str) -> str:
        qt = question_text.lower()
        for key, ans in QUESTION_ANSWERS.items():
            if key in qt:
                return ans
        # default if nothing matched
        return "NA"