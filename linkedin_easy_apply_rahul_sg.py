"""
LinkedIn Easy Apply Bot - Standalone Selenium Script
Applies to Easy Apply jobs in Singapore for Data Engineer roles.
Uses JavaScript clicks for reliability and scrolls modals properly.
"""

import time
import sys
import os
import traceback
from datetime import datetime
from urllib.parse import quote_plus

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)


# ──────────────────── CONFIG ────────────────────

USERNAME = "rahulpoolanchalil.au@gmail.com"
PASSWORD = "Linkedin@031986"

KEYWORDS = [
    "data engineer",
    "data engineering",
    "etl engineer",
    "data platform engineer",
    "analytics engineer",
]
LOCATION = "Singapore"
MAX_APPLICATIONS = 50

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
SCREENSHOT_DIR = os.path.join(LOG_DIR, "screenshots")


# ──────────────────── LOGGING ────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def screenshot(driver, label: str = "debug"):
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"ea_{label}_{ts}.png")
        driver.save_screenshot(path)
        log(f"  Screenshot: {path}")
    except Exception:
        pass


# ──────────────────── BROWSER ────────────────────

def create_driver():
    """Create a Chrome driver (visible window)."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    # Remove webdriver flag
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


# ──────────────────── JS HELPERS ────────────────────

def js_click(driver, element):
    """Click an element via JavaScript (most reliable)."""
    driver.execute_script("arguments[0].scrollIntoView({block:'center'}); arguments[0].click();", element)


def js_find_and_click_button(driver, button_texts):
    """
    Use JavaScript to find a button by its visible text (span or direct text).
    Scrolls into view and clicks. Returns matched text or empty string.
    """
    result = driver.execute_script("""
        var texts = arguments[0];
        var buttons = document.querySelectorAll('button');
        for (var t = 0; t < texts.length; t++) {
            for (var i = 0; i < buttons.length; i++) {
                var btn = buttons[i];
                var span = btn.querySelector('span');
                var txt = (span ? span.textContent : btn.textContent).trim();
                if (txt === texts[t] && btn.offsetParent !== null) {
                    btn.scrollIntoView({block: 'center'});
                    btn.click();
                    return texts[t];
                }
            }
        }
        return '';
    """, button_texts)
    return result or ""


def js_scroll_modal(driver):
    """Scroll the Easy Apply modal content to the bottom."""
    driver.execute_script("""
        var selectors = [
            '.jobs-easy-apply-content',
            '.artdeco-modal__content',
            '.jobs-easy-apply-modal__content'
        ];
        for (var s = 0; s < selectors.length; s++) {
            var el = document.querySelector(selectors[s]);
            if (el) {
                el.scrollTop = el.scrollHeight;
                return;
            }
        }
    """)
    time.sleep(0.2)


# ──────────────────── LOGIN ────────────────────

def login(driver):
    log("Navigating to LinkedIn login...")
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)

    try:
        user_field = driver.find_element(By.ID, "username")
        pass_field = driver.find_element(By.ID, "password")
        user_field.clear()
        user_field.send_keys(USERNAME)
        pass_field.clear()
        pass_field.send_keys(PASSWORD)

        submit = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit.click()
        log("Credentials submitted. Waiting for login...")
        time.sleep(5)

        # Check for verification/captcha
        if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            log("*** VERIFICATION REQUIRED - Please complete it in the browser ***")
            log("Waiting 60 seconds for manual verification...")
            time.sleep(60)

        log(f"Logged in. Current URL: {driver.current_url}")
    except Exception as e:
        log(f"Login issue: {e}")
        screenshot(driver, "login_issue")
        log("Please log in manually. Waiting 30 seconds...")
        time.sleep(30)


# ──────────────────── SEARCH ────────────────────

def build_search_url(keywords: str, location: str) -> str:
    kw = quote_plus(keywords)
    loc = quote_plus(location)
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_AL=true&sortBy=R"


def get_easy_apply_jobs(driver) -> list:
    """Return list of (index, card_text) for Easy Apply jobs not yet applied."""
    cards = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
    jobs = []
    for i, card in enumerate(cards):
        try:
            text = (card.text or "").lower()
            if "applied" in text or "see application" in text:
                continue
            if "easy apply" in text:
                jobs.append(i)
        except StaleElementReferenceException:
            continue
    return jobs


def click_job_card(driver, index: int):
    """Click on a job card by index."""
    cards = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
    if index >= len(cards):
        return False
    card = cards[index]
    try:
        link = card.find_element(By.TAG_NAME, "a")
        js_click(driver, link)
        time.sleep(1)
        return True
    except Exception:
        return False


def get_job_title(driver) -> str:
    """Try to get current job title from the detail pane."""
    for xp in [
        "//h1[contains(@class,'t-24')]",
        "//h2[contains(@class,'job-title')]",
        "//a[contains(@class,'job-card-list__title')]",
    ]:
        try:
            return driver.find_element(By.XPATH, xp).text.strip()
        except NoSuchElementException:
            continue
    return "(unknown title)"


# ──────────────────── EASY APPLY MODAL ────────────────────

def click_easy_apply_button(driver) -> bool:
    """Find and click the Easy Apply button on the job detail page."""
    xpaths = [
        "//button[contains(@class,'jobs-apply-button') and contains(@aria-label, 'Easy')]",
        "//button[contains(@aria-label, 'Easy Apply')]",
        "//button[.//span[contains(text(),'Easy Apply')]]",
    ]
    for xp in xpaths:
        try:
            btn = driver.find_element(By.XPATH, xp)
            if btn.is_displayed():
                js_click(driver, btn)
                time.sleep(1.5)
                return True
        except NoSuchElementException:
            continue

    # JS fallback
    clicked = js_find_and_click_button(driver, ["Easy Apply"])
    if clicked:
        time.sleep(1.5)
        return True

    return False


def _is_sponsorship_question(label_text: str) -> bool:
    """Check if a label is asking about visa sponsorship."""
    lbl = label_text.lower()
    return any(w in lbl for w in ["sponsor", "sponsorship", "visa sponsor"])


def _is_work_auth_question(label_text: str) -> bool:
    """Check if a label is asking about work authorization / right to work."""
    lbl = label_text.lower()
    return any(w in lbl for w in [
        "authoriz", "authoris", "right to work", "legally", "eligible to work",
        "work right", "permission to work", "entitled to work",
        "legally entitled", "valid visa", "work visa", "permanent residen",
    ])


def _smart_answer_for_select(label_text: str, options) -> str:
    """Pick the best dropdown option based on the question context. Returns option text or empty."""
    lbl = label_text.lower()

    # Sponsorship: answer "No" (don't need sponsorship)
    if _is_sponsorship_question(lbl):
        for opt in options:
            if (opt.text or "").strip().lower() == "no":
                return opt.text.strip()

    # Work authorization: answer "Yes"
    if _is_work_auth_question(lbl):
        for opt in options:
            if (opt.text or "").strip().lower() == "yes":
                return opt.text.strip()

    # Default: prefer "Yes", then first non-placeholder option
    for opt in options:
        if (opt.text or "").strip().lower() == "yes":
            return opt.text.strip()
    return ""


def _smart_answer_for_radio(label_text: str) -> str:
    """Return which radio label to prefer: 'yes' or 'no'."""
    lbl = label_text.lower()
    if _is_sponsorship_question(lbl):
        return "no"
    if _is_work_auth_question(lbl):
        return "yes"
    return "yes"  # Default: prefer Yes


def fill_form_fields(driver) -> bool:
    """Fill required form fields inside the Easy Apply modal. Returns True if anything filled."""
    filled = False
    modal_prefix = "//div[contains(@class,'jobs-easy-apply')]"

    # 1) Text/number inputs
    try:
        inputs = driver.find_elements(By.XPATH, f"{modal_prefix}//input[(@type='text' or @type='number' or not(@type))]")
        for inp in inputs:
            try:
                if inp.get_attribute("required") is None and inp.get_attribute("aria-required") != "true":
                    continue
                val = (inp.get_attribute("value") or "").strip()
                if val:
                    continue
                label_text = _get_label(driver, inp)
                inp.clear()
                if any(w in label_text for w in ["year", "experience"]):
                    inp.send_keys("5")
                elif any(w in label_text for w in ["city", "location"]):
                    inp.send_keys("Singapore")
                elif any(w in label_text for w in ["salary", "pay", "rate", "compensation"]):
                    inp.send_keys("120000")
                elif any(w in label_text for w in ["phone", "mobile"]):
                    inp.send_keys("0434973771")
                elif any(w in label_text for w in ["url", "website", "linkedin", "github"]):
                    inp.send_keys("https://www.linkedin.com/in/rahulpoolanchalil/")
                elif _is_sponsorship_question(label_text):
                    inp.send_keys("No")
                elif _is_work_auth_question(label_text):
                    inp.send_keys("Yes")
                elif any(w in label_text for w in ["notice period", "notice"]):
                    inp.send_keys("2 weeks")
                elif any(w in label_text for w in ["start date", "when can you start", "available"]):
                    inp.send_keys("Immediately")
                else:
                    inp.send_keys("5")
                filled = True
                log(f"    Filled input '{label_text}'")
                time.sleep(0.1)
            except (StaleElementReferenceException, Exception):
                continue
    except Exception:
        pass

    # 2) Textareas
    try:
        textareas = driver.find_elements(By.XPATH, f"{modal_prefix}//textarea")
        for ta in textareas:
            try:
                if ta.get_attribute("required") is None and ta.get_attribute("aria-required") != "true":
                    continue
                if (ta.get_attribute("value") or "").strip():
                    continue
                label_text = _get_label(driver, ta)
                ta.clear()
                if _is_sponsorship_question(label_text):
                    ta.send_keys("No, I do not require visa sponsorship. I have valid work authorization and can start immediately.")
                elif _is_work_auth_question(label_text):
                    ta.send_keys("Yes, I am legally authorized to work and do not require sponsorship.")
                elif any(w in label_text for w in ["cover letter", "why", "interest", "motivation"]):
                    ta.send_keys("I have 5+ years of experience in data engineering with expertise in Python, SQL, Spark, Airflow, and cloud platforms (AWS/GCP/Azure). I do not require sponsorship and can start immediately. I am keen to contribute to your team.")
                else:
                    ta.send_keys("I have 5+ years of experience in data engineering with expertise in Python, SQL, Spark, Airflow, and cloud platforms (AWS/GCP/Azure). I do not require sponsorship and am available to start immediately.")
                filled = True
                log(f"    Filled textarea '{label_text}'")
                time.sleep(0.1)
            except Exception:
                continue
    except Exception:
        pass

    # 3) Select dropdowns
    try:
        selects = driver.find_elements(By.XPATH, f"{modal_prefix}//select")
        for sel in selects:
            try:
                select_obj = Select(sel)
                current = (sel.get_attribute("value") or "").strip()
                if current:
                    continue
                label_text = _get_label(driver, sel)
                options = select_obj.options

                # Smart answer based on question context
                answer = _smart_answer_for_select(label_text, options)
                if answer:
                    select_obj.select_by_visible_text(answer)
                    filled = True
                    log(f"    Selected '{answer}' in dropdown '{label_text}'")
                elif len(options) > 1:
                    select_obj.select_by_index(1)
                    filled = True
                    log(f"    Selected first option in dropdown '{label_text}'")
                time.sleep(0.1)
            except Exception:
                continue
    except Exception:
        pass

    # 4) Radio buttons
    try:
        fieldsets = driver.find_elements(By.XPATH, f"{modal_prefix}//fieldset[.//input[@type='radio']]")
        for fs in fieldsets:
            try:
                radios = fs.find_elements(By.XPATH, ".//input[@type='radio']")
                if any(r.is_selected() for r in radios):
                    continue
                # Get the fieldset question text
                question_text = ""
                try:
                    legend = fs.find_element(By.TAG_NAME, "legend")
                    question_text = (legend.text or "").lower()
                except Exception:
                    question_text = (fs.text or "").lower()

                preferred = _smart_answer_for_radio(question_text)

                clicked_radio = False
                for r in radios:
                    try:
                        label = r.find_element(By.XPATH, "ancestor::label | following-sibling::label | ../label")
                        label_txt = (label.text or "").strip().lower()
                        if label_txt == preferred:
                            js_click(driver, r)
                            clicked_radio = True
                            filled = True
                            log(f"    Selected '{preferred}' for '{question_text[:60]}'")
                            break
                    except Exception:
                        continue
                if not clicked_radio and radios:
                    js_click(driver, radios[0])
                    filled = True
                    log(f"    Selected first radio for '{question_text[:60]}'")
                time.sleep(0.1)
            except Exception:
                continue
    except Exception:
        pass

    return filled


def _get_label(driver, element) -> str:
    """Get label text for a form field."""
    try:
        el_id = element.get_attribute("id")
        if el_id:
            label = driver.find_element(By.XPATH, f"//label[@for='{el_id}']")
            return (label.text or "").lower()
    except Exception:
        pass
    try:
        aria = element.get_attribute("aria-label") or ""
        if aria:
            return aria.lower()
    except Exception:
        pass
    return ""


def _get_modal_progress(driver) -> str:
    """Get the current progress indicator text from the Easy Apply modal (e.g. 'Step 2 of 5')."""
    try:
        progress = driver.find_element(By.XPATH, "//div[contains(@class,'jobs-easy-apply')]//span[contains(@class,'artdeco-completeness')]")
        return (progress.get_attribute("aria-valuenow") or "") + "/" + (progress.get_attribute("aria-valuemax") or "")
    except Exception:
        pass
    try:
        progress = driver.find_element(By.XPATH, "//div[contains(@class,'jobs-easy-apply')]//progress")
        return (progress.get_attribute("value") or "") + "/" + (progress.get_attribute("max") or "")
    except Exception:
        pass
    # Fallback: grab the modal header text
    try:
        header = driver.find_element(By.XPATH, "//div[contains(@class,'jobs-easy-apply')]//h3")
        return header.text.strip()
    except Exception:
        return ""


def process_easy_apply_modal(driver) -> bool:
    """
    Navigate through the Easy Apply modal steps.
    Always fills form fields FIRST, then clicks Next/Submit.
    Detects when stuck (same progress after click).
    Returns True if application was submitted.
    """
    SUBMIT_TEXTS = ["Submit application"]
    NEXT_TEXTS = ["Review your application", "Review", "Continue to next step", "Next"]
    max_steps = 25
    stuck_count = 0
    last_progress = ""

    for step in range(max_steps):
        log(f"  Step {step + 1}/{max_steps}")

        # Scroll modal down
        js_scroll_modal(driver)

        # Get current progress to detect if we're stuck
        current_progress = _get_modal_progress(driver)

        # ALWAYS fill form fields first before clicking any button
        filled = fill_form_fields(driver)
        if filled:
            js_scroll_modal(driver)

        # Try Submit first
        clicked = js_find_and_click_button(driver, SUBMIT_TEXTS)
        if clicked:
            log(f"    -> Clicked '{clicked}'")
            time.sleep(1.5)
            _handle_post_submit(driver)
            return True

        # Try Next/Continue/Review
        clicked = js_find_and_click_button(driver, NEXT_TEXTS)
        if clicked:
            log(f"    -> Clicked '{clicked}'")
            time.sleep(1)

            # Check if progress actually changed (detect stuck loops)
            new_progress = _get_modal_progress(driver)
            if new_progress and new_progress == current_progress:
                stuck_count += 1
                log(f"    Progress unchanged ({new_progress}). Stuck count: {stuck_count}")
                if stuck_count >= 3:
                    log(f"    Stuck for 3 attempts. Checking for validation errors...")
                    screenshot(driver, f"step{step+1}_stuck")
                    # Check errors
                    try:
                        errors = driver.find_elements(By.XPATH, "//div[contains(@class,'artdeco-inline-feedback--error')]")
                        visible_errors = [e.text for e in errors if e.is_displayed() and e.text.strip()]
                        if visible_errors:
                            log(f"    Validation errors: {visible_errors}")
                    except Exception:
                        pass
                    log(f"    Giving up on this application.")
                    break
            else:
                stuck_count = 0  # Reset stuck counter on progress
            last_progress = new_progress
            continue

        # No button found at all
        log(f"    No button found. Checking for errors...")
        screenshot(driver, f"step{step+1}_no_button")

        try:
            errors = driver.find_elements(By.XPATH, "//div[contains(@class,'artdeco-inline-feedback--error')]")
            visible_errors = [e.text for e in errors if e.is_displayed() and e.text.strip()]
            if visible_errors:
                log(f"    Validation errors: {visible_errors}")
        except Exception:
            pass

        log(f"    Breaking at step {step + 1}.")
        break

    # Close modal if not submitted
    _close_modal(driver)
    return False


def _handle_post_submit(driver):
    """Click Done/Dismiss after successful submission."""
    time.sleep(1)
    clicked = js_find_and_click_button(driver, ["Done", "Dismiss"])
    if clicked:
        log(f"    -> Clicked '{clicked}' (post-submit)")
    time.sleep(0.5)


def _close_modal(driver):
    """Close the Easy Apply modal (dismiss + discard if needed)."""
    try:
        dismiss = driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']")
        js_click(driver, dismiss)
        time.sleep(0.5)
    except NoSuchElementException:
        return
    try:
        discard = driver.find_element(By.XPATH, "//button[contains(., 'Discard')]")
        js_click(driver, discard)
        time.sleep(0.5)
    except NoSuchElementException:
        pass


# ──────────────────── MAIN LOOP ────────────────────

def _ensure_easy_apply_filter(driver):
    """Click the Easy Apply filter button if it's not already active."""
    try:
        # Check if Easy Apply filter pill is already selected
        active = driver.find_elements(By.XPATH,
            "//button[contains(@class,'artdeco-pill--selected') and contains(.,'Easy Apply')]")
        if active:
            log("  Easy Apply filter already active.")
            return

        # Try clicking the Easy Apply filter button/pill
        easy_apply_btns = [
            "//button[contains(.,'Easy Apply') and contains(@class,'artdeco-pill')]",
            "//button[contains(@aria-label,'Easy Apply filter')]",
            "//button[.//span[text()='Easy Apply']]",
        ]
        for xp in easy_apply_btns:
            try:
                btn = driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    js_click(driver, btn)
                    log("  Clicked Easy Apply filter button.")
                    time.sleep(1)
                    return
            except NoSuchElementException:
                continue

        # JS fallback
        clicked = js_find_and_click_button(driver, ["Easy Apply"])
        if clicked:
            log("  JS clicked Easy Apply filter.")
            time.sleep(1)
    except Exception as e:
        log(f"  Could not set Easy Apply filter: {e}")


def apply_to_jobs(driver, keyword: str, applied_count: int) -> int:
    """Search for jobs with a keyword and apply. Returns updated applied count."""
    url = build_search_url(keyword, LOCATION)
    log(f"\n{'='*60}")
    log(f"Searching: '{keyword}' in {LOCATION}")
    log(f"{'='*60}")
    driver.get(url)
    time.sleep(2)

    # Ensure Easy Apply filter is active
    _ensure_easy_apply_filter(driver)
    time.sleep(1)

    job_indices = get_easy_apply_jobs(driver)
    log(f"Found {len(job_indices)} Easy Apply jobs on this page")

    for idx in job_indices:
        if applied_count >= MAX_APPLICATIONS:
            log(f"Reached max applications ({MAX_APPLICATIONS}). Stopping.")
            return applied_count

        if not click_job_card(driver, idx):
            continue

        title = get_job_title(driver)
        log(f"\nJob #{applied_count + 1}: {title}")

        if not click_easy_apply_button(driver):
            log(f"  No Easy Apply button found. Skipping.")
            continue

        success = process_easy_apply_modal(driver)
        if success:
            applied_count += 1
            log(f"  *** APPLIED SUCCESSFULLY *** (Total: {applied_count})")
        else:
            log(f"  Could not complete application. Skipping.")

        # Go back to search results
        driver.get(url)
        time.sleep(2)
        # Re-fetch job indices since page reloaded
        job_indices_new = get_easy_apply_jobs(driver)
        log(f"  Back to search. {len(job_indices_new)} Easy Apply jobs remaining.")

    return applied_count


def main():
    log("=" * 60)
    log("LinkedIn Easy Apply Bot")
    log(f"Location: {LOCATION}")
    log(f"Keywords: {', '.join(KEYWORDS)}")
    log(f"Max applications: {MAX_APPLICATIONS}")
    log("=" * 60)

    driver = create_driver()
    applied_count = 0

    try:
        login(driver)

        for keyword in KEYWORDS:
            if applied_count >= MAX_APPLICATIONS:
                break
            applied_count = apply_to_jobs(driver, keyword, applied_count)

        log(f"\n{'='*60}")
        log(f"DONE! Applied to {applied_count} jobs.")
        log(f"{'='*60}")

    except KeyboardInterrupt:
        log("\nStopped by user.")
    except Exception as e:
        log(f"\nFATAL ERROR: {e}")
        log(traceback.format_exc())
        screenshot(driver, "fatal_error")
    finally:
        log("Done. Browser stays open for 5 minutes then closes.")
        time.sleep(300)
        driver.quit()


if __name__ == "__main__":
    main()
