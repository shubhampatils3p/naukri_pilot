import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
            options=options,
        )
        self.wait = WebDriverWait(self.driver, 20)

    def login(self):
        self.driver.get("https://www.naukri.com/")

        login_btn = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//a[@id='login_Layer'] | //a[contains(@href,'login')]")
            )
        )
        login_btn.click()

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

        email_input.clear()
        email_input.send_keys(self.config.email)
        password_input.clear()
        password_input.send_keys(self.config.password)

        login_button = self.wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "button.btn-primary.loginButton"
            ))
        )
        login_button.click()

        self.wait.until(lambda d: "naukri.com" in d.current_url)
        print("Logged in (popup closed)")

    def search_jobs(self):
        time.sleep(3)

        base = "https://www.naukri.com"
        keyword_slug = "-".join(self.config.keyword.split()).lower()
        location_slug = "-".join(self.config.location.split()).lower()
        search_url = f"{base}/{keyword_slug}-jobs-in-{location_slug}"

        print(f"Opening search URL: {search_url}")
        self.driver.get(search_url)

        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Search page loaded")

        try:
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
            time.sleep(3)
        except Exception:
            print("Search bar not found or not clickable, relying on URL filters only")

    def get_job_cards(self):
        cards = self.driver.find_elements(By.CSS_SELECTOR, "div.srp-jobtuple-wrapper")
        visible_cards = []
        for card in cards:
            try:
                if card.is_displayed():
                    visible_cards.append(card)
            except Exception:
                pass
        print(f"get_job_cards: found {len(visible_cards)} visible cards")
        return visible_cards

    def apply_to_jobs(self):
        applied = 0
        results = []
        processed_job_keys = set()
        page_no = 1
        max_pages = 15

        while applied < self.config.max_jobs and page_no <= max_pages:
            if not self._ensure_results_page():
                print(f"Could not return to results page {page_no}, stopping")
                break

            time.sleep(2)

            try:
                self.wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.srp-jobtuple-wrapper")
                    )
                )
                print(f"Job tuple wrappers detected on page {page_no}")
            except Exception:
                print(f"Explicit wait for job tuple wrappers timed out on page {page_no}")

            cards = self.get_job_cards()
            if not cards:
                print(f"No job cards detected on page {page_no}, stopping")
                break

            print(f"Found {len(cards)} cards on page {page_no}")

            page_processed = 0

            for idx in range(len(cards)):
                if applied >= self.config.max_jobs:
                    break

                if not self._ensure_results_page():
                    print(f"[Page {page_no} | {idx}] Could not return to results page, stopping page")
                    break

                cards = self.get_job_cards()
                if idx >= len(cards):
                    break

                card = cards[idx]
                title_text = "(unknown)"
                company_text = ""
                href = ""
                job_key = None

                try:
                    if len(self.driver.window_handles) > 0:
                        self.driver.switch_to.window(self.driver.window_handles[0])

                    job_link = card.find_element(By.CSS_SELECTOR, "a.title")
                    href = (job_link.get_attribute("href") or "").strip()
                    title_text = (job_link.text or "").strip() or "(no title)"
                    company_text = self._safe_find_text(card, [
                        "a.comp-name",
                        "span.comp-name",
                        ".comp-name"
                    ])
                    job_key = f"{title_text}|{company_text}|{href}"

                    if job_key in processed_job_keys:
                        print(f"[Page {page_no} | {idx}] Duplicate job, skipping: {title_text}")
                        continue

                    processed_job_keys.add(job_key)
                    page_processed += 1

                    print(f"[Page {page_no} | {idx}] Opening job: {title_text}")
                    self.driver.execute_script("arguments[0].click();", job_link)
                    time.sleep(3)

                    if len(self.driver.window_handles) > 1:
                        self.driver.switch_to.window(self.driver.window_handles[-1])

                    current_job_url = self.driver.current_url

                    if self._is_external_company_site(current_job_url):
                        print(f"[Page {page_no} | {idx}] External company site detected, skipping")
                        results.append({
                            "title": title_text,
                            "status": "skipped",
                            "reason": "External company site",
                            "url": current_job_url or href,
                        })
                        self._close_extra_tab()
                        continue

                    apply_buttons = self.driver.find_elements(
                        By.XPATH,
                        "//a[contains(., 'Apply') or contains(., 'APPLY') or contains(., 'Apply now') or contains(., 'I am interested')]"
                        " | //button[contains(., 'Apply') or contains(., 'APPLY') or contains(., 'Apply now') or contains(., 'I am interested')]"
                    )

                    if not apply_buttons:
                        print(f"[Page {page_no} | {idx}] No apply button, skipping")
                        results.append({
                            "title": title_text,
                            "status": "skipped",
                            "reason": "No apply button",
                            "url": current_job_url or href,
                        })
                        self._close_extra_tab()
                        continue

                    apply_text = ((apply_buttons[0].text or "").strip().lower()) if apply_buttons else ""
                    if "company site" in apply_text or "external" in apply_text:
                        print(f"[Page {page_no} | {idx}] Apply on company site detected, skipping")
                        results.append({
                            "title": title_text,
                            "status": "skipped",
                            "reason": "Apply on company site",
                            "url": current_job_url or href,
                        })
                        self._close_extra_tab()
                        continue

                    self.driver.execute_script("arguments[0].click();", apply_buttons[0])
                    time.sleep(4)

                    if self._is_external_company_site(self.driver.current_url):
                        print(f"[Page {page_no} | {idx}] Redirected to company site after apply, skipping")
                        results.append({
                            "title": title_text,
                            "status": "skipped",
                            "reason": "Redirected to company site after apply",
                            "url": self.driver.current_url or current_job_url or href,
                        })
                        self._close_extra_tab()
                        continue

                    success_chat, reason_chat = self._handle_chatbot_question(title_text)

                    if success_chat:
                        print(f"[Page {page_no} | {idx}] Chatbot completed for '{title_text}'")
                        applied += 1
                        results.append({
                            "title": title_text,
                            "status": "applied",
                            "reason": "",
                            "url": current_job_url or href,
                        })
                        self._close_extra_tab()
                        continue

                    if reason_chat not in ("Chatbot not visible", "No chatbot question found"):
                        print(f"[Page {page_no} | {idx}] Skipping due to chatbot issue: {reason_chat}")
                        results.append({
                            "title": title_text,
                            "status": "skipped",
                            "reason": reason_chat,
                            "url": current_job_url or href,
                        })
                        self._close_extra_tab()
                        continue

                    extra_fields = self.driver.find_elements(
                        By.XPATH,
                        "//input[@type='text' or @type='number' or @type='email']"
                    )
                    dropdowns = self.driver.find_elements(By.TAG_NAME, "select")

                    if len(extra_fields) > 3 or len(dropdowns) > 0:
                        print(f"[Page {page_no} | {idx}] Complex form detected for '{title_text}', skipping")
                        results.append({
                            "title": title_text,
                            "status": "skipped",
                            "reason": "Complex form (non-chatbot)",
                            "url": current_job_url or href,
                        })
                    else:
                        if self._is_apply_finished():
                            print(f"[Page {page_no} | {idx}] Applied (simple apply) for '{title_text}'")
                            applied += 1
                            results.append({
                                "title": title_text,
                                "status": "applied",
                                "reason": "",
                                "url": current_job_url or href,
                            })
                        else:
                            print(f"[Page {page_no} | {idx}] Apply not confirmed for '{title_text}', skipping")
                            results.append({
                                "title": title_text,
                                "status": "skipped",
                                "reason": "Apply not confirmed",
                                "url": current_job_url or href,
                            })

                    self._close_extra_tab()

                except Exception as e:
                    print(f"[Page {page_no} | {idx}] Problematic job, skipping. Error: {e}")
                    results.append({
                        "title": title_text,
                        "status": "skipped",
                        "reason": f"Error during apply flow: {e}",
                        "url": href,
                    })
                    try:
                        self._close_extra_tab()
                    except Exception:
                        pass

                self._ensure_results_page()

            if applied >= self.config.max_jobs:
                break

            if page_processed == 0:
                print(f"No new jobs processed on page {page_no}, stopping")
                break

            if not self._go_to_next_results_page(page_no):
                print("No more result pages available")
                break

            page_no += 1

        print(f"Applied to {applied} jobs out of requested {self.config.max_jobs}")
        skipped = len([r for r in results if r["status"] == "skipped"])

        return {
            "applied": applied,
            "skipped": skipped,
            "details": results,
        }

    def _ensure_results_page(self) -> bool:
        try:
            if len(self.driver.window_handles) > 1:
                self._close_extra_tab()

            self.driver.switch_to.window(self.driver.window_handles[0])

            if "naukri.com" not in self.driver.current_url:
                return False

            if "/job-listings-" in self.driver.current_url:
                self.driver.back()
                time.sleep(3)

            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.srp-jobtuple-wrapper"))
            )
            return True
        except Exception:
            return False
   
    def _is_external_company_site(self, url: str) -> bool:
        if not url:
            return False

        url = url.lower()
        blocked = [
            "naukri.com",
            "www.naukri.com",
            "hirect.in",
        ]

        for item in blocked:
            if item in url:
                return False

        return True
     
    def _safe_find_text(self, parent, selectors):
        for selector in selectors:
            try:
                el = parent.find_element(By.CSS_SELECTOR, selector)
                txt = (el.text or "").strip()
                if txt:
                    return txt
            except Exception:
                pass
        return ""

    def _close_extra_tab(self):
        try:
            while len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception as e:
            print(f"_close_extra_tab: error while closing tabs: {e}")

    def quit(self):
        self.driver.quit()

    def _handle_chatbot_question(self, title_text: str):
        try:
            container = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.chatbot_DrawerContentWrapper")
                )
            )
        except Exception:
            return False, "Chatbot not visible"

        answered_questions = set()
        max_steps = 10

        for step in range(max_steps):
            try:
                question_text = self._get_latest_chatbot_question(container)

                if not question_text:
                    if self._is_apply_finished():
                        return True, ""
                    if self._has_thank_you_message(container):
                        return True, ""
                    try:
                        if not container.is_displayed():
                            return True, ""
                    except Exception:
                        return True, ""
                    return False, "No chatbot question found"

                normalized_q = " ".join(question_text.lower().split())

                if normalized_q in answered_questions:
                    if self._is_apply_finished() or self._has_thank_you_message(container):
                        return True, ""
                    try:
                        if not container.is_displayed():
                            return True, ""
                    except Exception:
                        return True, ""
                    if self._wait_for_new_bot_message(container, previous_question=normalized_q, timeout=8):
                        new_q = self._get_latest_chatbot_question(container)
                        new_norm = " ".join((new_q or "").lower().split())
                        if new_q and new_norm != normalized_q:
                            continue
                    return False, f"Chatbot stuck on same question: {question_text}"

                answered_questions.add(normalized_q)

                print(f"Chatbot question for '{title_text}': {question_text!r}")

                answer = self._get_answer_for_chatbot_question(question_text)
                print(f"Answering chatbot with: {answer!r}")

                if not answer or answer == "NA":
                    return False, f"No mapped answer for question: {question_text}"

                before_bot_count = self._get_bot_message_count(container)
                before_user_count = self._get_user_message_count(container)

                if self._has_radio_question(container):
                    if not self._click_chatbot_radio_option(container, answer):
                        return False, f"Could not select radio option for: {question_text}"

                    if not self._wait_until_radio_selected(container, answer, timeout=5):
                        return False, f"Radio option not selected for: {question_text}"

                    if not self._click_chatbot_save(container):
                        if self._is_apply_finished() or self._has_thank_you_message(container):
                            return True, ""
                        try:
                            if not container.is_displayed():
                                return True, ""
                        except Exception:
                            return True, ""
                        return False, f"Could not click Save for: {question_text}"

                    if self._wait_for_chat_progress(container, before_bot_count, before_user_count, timeout=20):
                        if self._has_thank_you_message(container) or self._is_apply_finished():
                            return True, ""

                        try:
                            latest_after = self._get_latest_chatbot_question(container)
                            normalized_after = " ".join((latest_after or "").lower().split())
                            if latest_after and normalized_after != normalized_q:
                                continue
                        except Exception:
                            pass

                        try:
                            if not container.is_displayed():
                                return True, ""
                        except Exception:
                            return True, ""

                        if self._is_apply_finished():
                            return True, ""

                        continue

                    if self._is_apply_finished() or self._has_thank_you_message(container):
                        return True, ""
                    try:
                        if not container.is_displayed():
                            return True, ""
                    except Exception:
                        return True, ""
                    return False, f"No chat progress after radio answer for: {question_text}"

                if not self._type_chatbot_answer(container, answer):
                    if self._is_apply_finished() or self._has_thank_you_message(container):
                        return True, ""
                    try:
                        if not container.is_displayed():
                            return True, ""
                    except Exception:
                        return True, ""
                    return False, f"Could not answer chatbot question: {question_text}"

                if self._wait_for_chat_progress(container, before_bot_count, before_user_count, timeout=20):
                    if self._has_thank_you_message(container) or self._is_apply_finished():
                        return True, ""

                    try:
                        latest_after = self._get_latest_chatbot_question(container)
                        normalized_after = " ".join((latest_after or "").lower().split())
                        if latest_after and normalized_after != normalized_q:
                            continue
                    except Exception:
                        pass

                    try:
                        if not container.is_displayed():
                            return True, ""
                    except Exception:
                        return True, ""

                    if self._is_apply_finished():
                        return True, ""

                    continue

                if self._is_apply_finished() or self._has_thank_you_message(container):
                    return True, ""
                try:
                    if not container.is_displayed():
                        return True, ""
                except Exception:
                    return True, ""

                return False, f"No next chatbot question after answering: {question_text}"

            except Exception as e:
                print(f"_handle_chatbot_question step error for '{title_text}': {e}")
                if self._is_apply_finished():
                    return True, ""
                try:
                    if not container.is_displayed():
                        return True, ""
                except Exception:
                    return True, ""
                return False, f"Error handling chatbot question: {e}"

        if self._is_apply_finished() or self._has_thank_you_message(container):
            return True, ""
        try:
            if not container.is_displayed():
                return True, ""
        except Exception:
            return True, ""

        return False, f"Exceeded chatbot question limit ({max_steps})"

    def _get_answer_for_chatbot_question(self, question_text: str) -> str:
        qt = question_text.lower()
        for key, ans in QUESTION_ANSWERS.items():
            if key in qt:
                return ans
        return "NA"

    def _get_latest_chatbot_question(self, container):
        selectors = [
            "div.chatbot_MessageContainer li.botItem.chatbot_ListItem div.botMsg span",
            "ul.list li.botItem.chatbot_ListItem div.botMsg span",
            "li.botItem div.botMsg span",
            "div.botMsg span"
        ]

        texts = []
        for selector in selectors:
            try:
                spans = container.find_elements(By.CSS_SELECTOR, selector)
                for s in spans:
                    try:
                        txt = (s.text or "").strip()
                        if txt:
                            texts.append(txt)
                    except Exception:
                        pass
            except Exception:
                pass

        if texts:
            return texts[-1]
        return None

    def _has_radio_question(self, container) -> bool:
        try:
            radio_wrap = container.find_elements(By.CSS_SELECTOR, "div.singleselect-radiobutton")
            for el in radio_wrap:
                try:
                    if el.is_displayed():
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def _click_chatbot_radio_option(self, container, answer: str) -> bool:
        wanted = (answer or "").strip().lower()

        try:
            radio_containers = container.find_elements(By.CSS_SELECTOR, "div.ssrc__radio-btn-container")
            for item in radio_containers:
                try:
                    label = item.find_element(By.CSS_SELECTOR, "label.ssrc__label")
                    text = (label.text or "").strip().lower()
                    if text == wanted:
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", label)
                        try:
                            label.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", label)
                        time.sleep(1)
                        if self._is_radio_answer_selected(container, answer):
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        try:
            radios = container.find_elements(By.CSS_SELECTOR, "input.ssrc__radio")
            for radio in radios:
                try:
                    val = (radio.get_attribute("value") or "").strip().lower()
                    rid = (radio.get_attribute("id") or "").strip().lower()
                    if val == wanted or rid == wanted:
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", radio)
                        try:
                            radio.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", radio)
                        time.sleep(1)
                        if self._is_radio_answer_selected(container, answer):
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        return False

    def _wait_until_radio_selected(self, container, answer: str, timeout: int = 5) -> bool:
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                if self._is_radio_answer_selected(container, answer):
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _is_radio_answer_selected(self, container, answer: str) -> bool:
        wanted = (answer or "").strip().lower()

        radios = container.find_elements(By.CSS_SELECTOR, "input.ssrc__radio")
        for radio in radios:
            try:
                val = (radio.get_attribute("value") or "").strip().lower()
                rid = (radio.get_attribute("id") or "").strip().lower()
                checked_attr = radio.get_attribute("checked")
                selected = radio.is_selected()
                if val == wanted or rid == wanted:
                    if selected or checked_attr is not None:
                        return True
            except Exception:
                pass

        return False

    def _click_chatbot_save(self, container) -> bool:
        selectors = [
            "div.sendMsgbtn_container div.sendMsg",
            "div.sendMsg",
            "div.send"
        ]

        for selector in selectors:
            try:
                buttons = container.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    try:
                        text = (btn.text or "").strip().lower()
                        if btn.is_displayed() and "save" in text:
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            try:
                                btn.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(2)
                            return True
                    except Exception:
                        pass
            except Exception:
                pass

        return False

    def _type_chatbot_answer(self, container, answer: str) -> bool:
        input_divs = container.find_elements(
            By.CSS_SELECTOR,
            "div.textArea[contenteditable='true']"
        )

        visible_input = None
        for el in input_divs:
            try:
                if el.is_displayed() and el.size["width"] > 0 and el.size["height"] > 0:
                    visible_input = el
                    break
            except Exception:
                pass

        if not visible_input:
            return False

        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", visible_input)
            self.driver.execute_script("arguments[0].click();", visible_input)
            time.sleep(0.5)
        except Exception:
            pass

        try:
            visible_input.send_keys(Keys.CONTROL, "a")
            visible_input.send_keys(Keys.DELETE)
            time.sleep(0.2)
        except Exception:
            pass

        try:
            visible_input.send_keys(answer)
            time.sleep(0.8)
        except Exception:
            return False

        entered_text = ""
        try:
            entered_text = (visible_input.text or "").strip()
        except Exception:
            pass

        if not entered_text:
            try:
                self.driver.execute_script("arguments[0].innerText = arguments[1];", visible_input, answer)
                time.sleep(0.5)
            except Exception:
                pass

        return self._click_chatbot_send(container)

    def _click_chatbot_send(self, container) -> bool:
        send_selectors = [
            "div.sendMsgbtn_container div.sendMsg",
            "div.sendMsg",
            "button[type='button']"
        ]

        for selector in send_selectors:
            try:
                buttons = container.find_elements(By.CSS_SELECTOR, selector)
                for btn in buttons:
                    try:
                        text = (btn.text or "").strip().lower()
                        if not btn.is_displayed():
                            continue
                        if "save" in text:
                            continue
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        try:
                            btn.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1.5)
                        return True
                    except Exception:
                        pass
            except Exception:
                pass

        return False

    def _is_apply_finished(self) -> bool:
    # Apply confirmation page
        try:
            layout = (self.driver.find_element(By.CSS_SELECTOR, "meta[name='atdlayout']").get_attribute("content") or "").strip().lower()
            title = (self.driver.title or "").strip().lower()
            if layout == "jobapplied" or "apply confirmation" in title:
                return True
        except Exception:
            pass

        success_xpaths = [
            "//*[contains(text(),'applied')]",
            "//*[contains(text(),'Application sent')]",
            "//*[contains(text(),'successfully applied')]",
            "//*[contains(text(),'Your application has been submitted')]"
        ]

        for xp in success_xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                for el in els:
                    try:
                        if el.is_displayed():
                            return True
                    except Exception:
                        pass
            except Exception:
                pass

        return False

    def _get_bot_message_count(self, container) -> int:
        selectors = [
            "div.chatbot_MessageContainer li.botItem.chatbot_ListItem",
            "ul.list li.botItem.chatbot_ListItem"
        ]
        for selector in selectors:
            try:
                msgs = container.find_elements(By.CSS_SELECTOR, selector)
                if msgs:
                    return len(msgs)
            except Exception:
                pass
        return 0

    def _get_user_message_count(self, container) -> int:
        selectors = [
            "div.chatbot_MessageContainer li.userItem.chatbot_ListItem",
            "ul.list li.userItem.chatbot_ListItem"
        ]
        for selector in selectors:
            try:
                msgs = container.find_elements(By.CSS_SELECTOR, selector)
                if msgs:
                    return len(msgs)
            except Exception:
                pass
        return 0

    def _wait_for_new_bot_message(self, container, previous_question: str, timeout: int = 8) -> bool:
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                if self._is_apply_finished() or self._has_thank_you_message(container):
                    return True

                latest = self._get_latest_chatbot_question(container)
                if latest:
                    normalized = " ".join(latest.lower().split())
                    if normalized != previous_question:
                        return True
            except Exception:
                pass
            time.sleep(0.7)
        return False

    def _wait_for_chat_progress(self, container, old_bot_count: int, old_user_count: int, timeout: int = 15) -> bool:
        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                if self._is_apply_finished() or self._has_thank_you_message(container):
                    return True

                try:
                    if not container.is_displayed():
                        return True
                except Exception:
                    return True

                new_bot_count = self._get_bot_message_count(container)
                new_user_count = self._get_user_message_count(container)

                if new_bot_count > old_bot_count or new_user_count > old_user_count:
                    return True
            except Exception:
                pass

            time.sleep(0.8)

        return False

    def _has_thank_you_message(self, container) -> bool:
        try:
            spans = container.find_elements(
                By.CSS_SELECTOR,
                "div.chatbot_MessageContainer li.botItem.chatbot_ListItem div.botMsg span, ul.list li.botItem.chatbot_ListItem div.botMsg span"
            )
            for s in spans:
                try:
                    txt = (s.text or "").strip().lower()
                    if "thank" in txt and "response" in txt:
                        return True
                except Exception:
                    pass
        except Exception:
            pass

        return False

    def _go_to_next_results_page(self, current_page_no: int) -> bool:
        try:
            pagination = self.driver.find_element(
                By.CSS_SELECTOR,
                "div.styles_pagination-cont__sWhS6 div.styles_pagination__oIvXh"
            )
        except Exception:
            print("Pagination container not found")
            return False

        current_url = self.driver.current_url

        # Capture first job title to detect change
        before_first_title = ""
        try:
            cards = self.get_job_cards()
            if cards:
                first_link = cards[0].find_element(By.CSS_SELECTOR, "a.title")
                before_first_title = (first_link.text or "").strip()
        except Exception:
            pass

        try:
            page_links = pagination.find_elements(By.CSS_SELECTOR, "div.styles_pages__v1rAK a")
        except Exception:
            page_links = []

        target_page = str(current_page_no + 1)
        target_link = None

        for link in page_links:
            try:
                text = (link.text or "").strip()
                if text == target_page:
                    target_link = link
                    break
            except Exception:
                pass

        if not target_link:
            # fallback: click Next
            try:
                next_btns = pagination.find_elements(
                    By.CSS_SELECTOR,
                    "a.styles_btn-secondary__2AsIP"
                )
                for btn in next_btns:
                    try:
                        text = (btn.text or "").strip().lower()
                        if "next" in text and btn.get_attribute("disabled") is None:
                            target_link = btn
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        if not target_link:
            print(f"No page link found for page {current_page_no + 1}")
            return False

        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", target_link
            )
            try:
                target_link.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", target_link)
            time.sleep(4)

            def page_changed(d):
                if d.current_url != current_url:
                    return True
                try:
                    new_cards = d.find_elements(By.CSS_SELECTOR, "div.srp-jobtuple-wrapper")
                    if not new_cards:
                        return False
                    new_first = new_cards[0].find_element(By.CSS_SELECTOR, "a.title")
                    new_first_title = (new_first.text or "").strip()
                    return new_first_title != before_first_title
                except Exception:
                    return False

            self.wait.until(page_changed)
            print(f"Moved to results page {current_page_no + 1}")
            return True
        except Exception as e:
            print(f"_go_to_next_results_page error: {e}")
            return False