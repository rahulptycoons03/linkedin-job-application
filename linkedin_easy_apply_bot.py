"""
LinkedIn Easy Apply Bot
=======================
Automatically applies to LinkedIn "Easy Apply" jobs using Selenium.

Usage:
    python linkedin_easy_apply_bot.py --profile profiles/my_profile.json

The bot will:
  1. Open Chrome and log into LinkedIn with your credentials
  2. Search for jobs matching your keywords and location
  3. Click "Easy Apply" on each job and fill out the application form
  4. Automatically answer common questions (experience, sponsorship, etc.)
  5. Submit the application and move on to the next job

Requirements:
  - Python 3.9+
  - Google Chrome browser installed
  - ChromeDriver (auto-installed via selenium)
"""

import json
import time
import sys
import os
import argparse
import traceback
from datetime import datetime
from urllib.parse import quote_plus

from selenium import webdriver
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


# ──────────────────────────────────────────────
#  CONFIGURATION (loaded from JSON profile)
# ──────────────────────────────────────────────

CONFIG = {}   # populated by load_config()

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
SCREENSHOT_DIR = os.path.join(LOG_DIR, "screenshots")


def load_config(profile_path: str) -> dict:
    """Load a JSON profile file and return the config dict."""
    if not os.path.isabs(profile_path):
        profile_path = os.path.join(SCRIPT_DIR, profile_path)
    if not os.path.exists(profile_path):
        print(f"ERROR: Profile file not found: {profile_path}")
        print("Please create a profile JSON file. See profiles/example_data_engineer.json")
        sys.exit(1)
    with open(profile_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Validate required fields
    required = ["linkedin_email", "linkedin_password", "keywords", "location"]
    for key in required:
        if key not in cfg or not cfg[key]:
            print(f"ERROR: Missing required field '{key}' in {profile_path}")
            sys.exit(1)

    # Set defaults for optional fields
    cfg.setdefault("max_applications", 50)
    cfg.setdefault("phone_number", "")
    cfg.setdefault("linkedin_profile_url", "")
    cfg.setdefault("years_of_experience", "5")
    cfg.setdefault("salary_expectation", "")
    cfg.setdefault("notice_period", "2 weeks")
    cfg.setdefault("requires_sponsorship", False)
    cfg.setdefault("work_authorized", True)
    cfg.setdefault("search_radius_km", 100)
    cfg.setdefault("cover_letter_text", "")
    cfg.setdefault("default_answer_text", "")
    cfg.setdefault("city_for_forms", cfg["location"].split(",")[0].strip())

    return cfg


# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────

def log(msg: str):
    """Print a timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def screenshot(driver, label: str = "debug"):
    """Save a screenshot for debugging."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"ea_{label}_{ts}.png")
        driver.save_screenshot(path)
        log(f"  Screenshot: {path}")
    except Exception:
        pass


# ──────────────────────────────────────────────
#  BROWSER SETUP
# ──────────────────────────────────────────────

def create_driver():
    """Create a visible Chrome browser window."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    # Hide the "automated browser" flag from LinkedIn
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


# ──────────────────────────────────────────────
#  JAVASCRIPT HELPERS (more reliable than Selenium clicks)
# ──────────────────────────────────────────────

def js_click(driver, element):
    """Click an element using JavaScript (bypasses overlay issues)."""
    driver.execute_script(
        "arguments[0].scrollIntoView({block:'center'}); arguments[0].click();",
        element,
    )


def js_find_and_click_button(driver, button_texts):
    """
    Find a visible button by its text content and click it via JS.
    Returns the matched text, or empty string if not found.
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


# ──────────────────────────────────────────────
#  LOGIN
# ──────────────────────────────────────────────

def login(driver):
    """Log into LinkedIn. Handles verification/captcha with manual wait."""
    log("Navigating to LinkedIn login...")
    driver.get("https://www.linkedin.com/login")
    time.sleep(2)

    try:
        user_field = driver.find_element(By.ID, "username")
        pass_field = driver.find_element(By.ID, "password")
        user_field.clear()
        user_field.send_keys(CONFIG["linkedin_email"])
        pass_field.clear()
        pass_field.send_keys(CONFIG["linkedin_password"])

        submit = driver.find_element(By.XPATH, "//button[@type='submit']")
        submit.click()
        log("Credentials submitted. Waiting for login...")
        time.sleep(5)

        # Check for verification / CAPTCHA
        if "checkpoint" in driver.current_url or "challenge" in driver.current_url:
            log("*** VERIFICATION REQUIRED ***")
            log("Please complete the CAPTCHA/verification in the browser window.")
            log("Waiting 60 seconds...")
            time.sleep(60)

        log(f"Logged in. Current URL: {driver.current_url}")
    except Exception as e:
        log(f"Login issue: {e}")
        screenshot(driver, "login_issue")
        log("Please log in manually in the browser window. Waiting 30 seconds...")
        time.sleep(30)


# ──────────────────────────────────────────────
#  JOB SEARCH
# ──────────────────────────────────────────────

def build_search_url(keywords: str, location: str) -> str:
    """Build a LinkedIn job search URL with Easy Apply filter."""
    kw = quote_plus(keywords)
    loc = quote_plus(location)
    radius = CONFIG.get("search_radius_km", 100)
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_AL=true&distance={radius}&sortBy=R"


def get_easy_apply_jobs(driver) -> list:
    """Return list of indices for Easy Apply job cards (skips already-applied)."""
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
    """Get the current job title from the detail pane."""
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


# ──────────────────────────────────────────────
#  EASY APPLY MODAL
# ──────────────────────────────────────────────

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

    # JavaScript fallback
    clicked = js_find_and_click_button(driver, ["Easy Apply"])
    if clicked:
        time.sleep(1.5)
        return True
    return False


# ──── Smart Answer Helpers ────

def _is_sponsorship_question(label_text: str) -> bool:
    lbl = label_text.lower()
    return any(w in lbl for w in ["sponsor", "sponsorship", "visa sponsor"])


def _is_work_auth_question(label_text: str) -> bool:
    lbl = label_text.lower()
    return any(w in lbl for w in [
        "authoriz", "authoris", "right to work", "legally", "eligible to work",
        "work right", "permission to work", "entitled to work",
        "legally entitled", "valid visa", "work visa", "permanent residen",
    ])


def _smart_answer_for_select(label_text: str, options) -> str:
    """Pick the best dropdown option based on the question."""
    lbl = label_text.lower()
    sponsorship_answer = "no" if not CONFIG.get("requires_sponsorship", False) else "yes"
    work_auth_answer = "yes" if CONFIG.get("work_authorized", True) else "no"

    if _is_sponsorship_question(lbl):
        for opt in options:
            if (opt.text or "").strip().lower() == sponsorship_answer:
                return opt.text.strip()

    if _is_work_auth_question(lbl):
        for opt in options:
            if (opt.text or "").strip().lower() == work_auth_answer:
                return opt.text.strip()

    # Default: prefer "Yes", then first non-placeholder option
    for opt in options:
        if (opt.text or "").strip().lower() == "yes":
            return opt.text.strip()
    return ""


def _smart_answer_for_radio(label_text: str) -> str:
    lbl = label_text.lower()
    if _is_sponsorship_question(lbl):
        return "no" if not CONFIG.get("requires_sponsorship", False) else "yes"
    if _is_work_auth_question(lbl):
        return "yes" if CONFIG.get("work_authorized", True) else "no"
    return "yes"


def _get_label(driver, element) -> str:
    """Get the label text for a form field."""
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


# ──── Form Filling ────

def fill_form_fields(driver) -> bool:
    """Fill all required form fields inside the Easy Apply modal."""
    filled = False
    modal = "//div[contains(@class,'jobs-easy-apply')]"
    years = CONFIG.get("years_of_experience", "5")
    city = CONFIG.get("city_for_forms", "Melbourne")
    salary = CONFIG.get("salary_expectation", "120000")
    phone = CONFIG.get("phone_number", "")
    profile_url = CONFIG.get("linkedin_profile_url", "")
    notice = CONFIG.get("notice_period", "2 weeks")
    cover_letter = CONFIG.get("cover_letter_text", "")
    default_text = CONFIG.get("default_answer_text", "")

    # 1) Text / number inputs
    try:
        inputs = driver.find_elements(By.XPATH, f"{modal}//input[(@type='text' or @type='number' or not(@type))]")
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
                    inp.send_keys(years)
                elif any(w in label_text for w in ["city", "location"]):
                    inp.send_keys(city)
                elif any(w in label_text for w in ["salary", "pay", "rate", "compensation"]):
                    inp.send_keys(salary)
                elif any(w in label_text for w in ["phone", "mobile"]):
                    inp.send_keys(phone or "0000000000")
                elif any(w in label_text for w in ["url", "website", "linkedin", "github"]):
                    inp.send_keys(profile_url or "https://www.linkedin.com/")
                elif _is_sponsorship_question(label_text):
                    inp.send_keys("No" if not CONFIG.get("requires_sponsorship") else "Yes")
                elif _is_work_auth_question(label_text):
                    inp.send_keys("Yes" if CONFIG.get("work_authorized") else "No")
                elif any(w in label_text for w in ["notice period", "notice"]):
                    inp.send_keys(notice)
                elif any(w in label_text for w in ["start date", "when can you start", "available"]):
                    inp.send_keys("Immediately")
                else:
                    inp.send_keys(years)  # safe default for numeric fields
                filled = True
                log(f"    Filled input '{label_text}'")
                time.sleep(0.1)
            except (StaleElementReferenceException, Exception):
                continue
    except Exception:
        pass

    # 2) Textareas
    try:
        textareas = driver.find_elements(By.XPATH, f"{modal}//textarea")
        for ta in textareas:
            try:
                if ta.get_attribute("required") is None and ta.get_attribute("aria-required") != "true":
                    continue
                if (ta.get_attribute("value") or "").strip():
                    continue
                label_text = _get_label(driver, ta)
                ta.clear()
                if _is_sponsorship_question(label_text):
                    sponsorship_text = CONFIG.get("sponsorship_answer_text",
                        "No, I do not require visa sponsorship. I have valid work authorization.")
                    ta.send_keys(sponsorship_text)
                elif _is_work_auth_question(label_text):
                    work_auth_text = CONFIG.get("work_auth_answer_text",
                        "Yes, I am legally authorized to work and do not require sponsorship.")
                    ta.send_keys(work_auth_text)
                elif any(w in label_text for w in ["cover letter", "why", "interest", "motivation"]):
                    ta.send_keys(cover_letter or default_text or "I am excited about this opportunity and believe my skills are a great match.")
                else:
                    ta.send_keys(default_text or "I am experienced and enthusiastic about this role.")
                filled = True
                log(f"    Filled textarea '{label_text}'")
                time.sleep(0.1)
            except Exception:
                continue
    except Exception:
        pass

    # 3) Select dropdowns
    try:
        selects = driver.find_elements(By.XPATH, f"{modal}//select")
        for sel in selects:
            try:
                select_obj = Select(sel)
                current = (sel.get_attribute("value") or "").strip()
                if current:
                    continue
                label_text = _get_label(driver, sel)
                options = select_obj.options
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
        fieldsets = driver.find_elements(By.XPATH, f"{modal}//fieldset[.//input[@type='radio']]")
        for fs in fieldsets:
            try:
                radios = fs.find_elements(By.XPATH, ".//input[@type='radio']")
                if any(r.is_selected() for r in radios):
                    continue
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


# ──── Modal Navigation ────

def _get_modal_progress(driver) -> str:
    """Get progress indicator from the Easy Apply modal."""
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
    try:
        header = driver.find_element(By.XPATH, "//div[contains(@class,'jobs-easy-apply')]//h3")
        return header.text.strip()
    except Exception:
        return ""


def process_easy_apply_modal(driver) -> bool:
    """
    Navigate through the Easy Apply modal steps.
    Fills form fields FIRST, then clicks Next/Review/Submit.
    Detects when stuck and gives up after 3 retries.
    Returns True if application was submitted successfully.
    """
    SUBMIT_TEXTS = ["Submit application"]
    NEXT_TEXTS = ["Review your application", "Review", "Continue to next step", "Next"]
    max_steps = 25
    stuck_count = 0

    for step in range(max_steps):
        log(f"  Step {step + 1}/{max_steps}")

        js_scroll_modal(driver)
        current_progress = _get_modal_progress(driver)

        # ALWAYS fill form fields first
        filled = fill_form_fields(driver)
        if filled:
            js_scroll_modal(driver)

        # Try Submit
        clicked = js_find_and_click_button(driver, SUBMIT_TEXTS)
        if clicked:
            log(f"    -> Clicked '{clicked}'")
            time.sleep(1.5)
            _handle_post_submit(driver)
            return True

        # Try Next / Review
        clicked = js_find_and_click_button(driver, NEXT_TEXTS)
        if clicked:
            log(f"    -> Clicked '{clicked}'")
            time.sleep(1)

            new_progress = _get_modal_progress(driver)
            if new_progress and new_progress == current_progress:
                stuck_count += 1
                log(f"    Progress unchanged ({new_progress}). Stuck count: {stuck_count}")
                if stuck_count >= 3:
                    log(f"    Stuck for 3 attempts. Taking screenshot...")
                    screenshot(driver, f"step{step+1}_stuck")
                    try:
                        errors = driver.find_elements(By.XPATH, "//div[contains(@class,'artdeco-inline-feedback--error')]")
                        visible = [e.text for e in errors if e.is_displayed() and e.text.strip()]
                        if visible:
                            log(f"    Validation errors: {visible}")
                    except Exception:
                        pass
                    log(f"    Giving up on this application.")
                    break
            else:
                stuck_count = 0
            continue

        # No button found
        log(f"    No button found. Breaking.")
        screenshot(driver, f"step{step+1}_no_button")
        break

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
    """Close the Easy Apply modal."""
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


# ──────────────────────────────────────────────
#  FILTER HELPERS
# ──────────────────────────────────────────────

def _ensure_easy_apply_filter(driver):
    """Make sure the Easy Apply filter is active on the search page."""
    try:
        active = driver.find_elements(By.XPATH,
            "//button[contains(@class,'artdeco-pill--selected') and contains(.,'Easy Apply')]")
        if active:
            log("  Easy Apply filter already active.")
            return

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

        clicked = js_find_and_click_button(driver, ["Easy Apply"])
        if clicked:
            log("  JS clicked Easy Apply filter.")
            time.sleep(1)
    except Exception as e:
        log(f"  Could not set Easy Apply filter: {e}")


# ──────────────────────────────────────────────
#  MAIN APPLICATION LOOP
# ──────────────────────────────────────────────

def apply_to_jobs(driver, keyword: str, applied_count: int) -> int:
    """Search for jobs with a keyword and apply. Returns updated count."""
    location = CONFIG["location"]
    max_apps = CONFIG.get("max_applications", 50)
    url = build_search_url(keyword, location)

    log(f"\n{'='*60}")
    log(f"Searching: '{keyword}' in {location}")
    log(f"{'='*60}")
    driver.get(url)
    time.sleep(2)

    _ensure_easy_apply_filter(driver)
    time.sleep(1)

    job_indices = get_easy_apply_jobs(driver)
    log(f"Found {len(job_indices)} Easy Apply jobs on this page")

    for idx in job_indices:
        if applied_count >= max_apps:
            log(f"Reached max applications ({max_apps}). Stopping.")
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
        job_indices_new = get_easy_apply_jobs(driver)
        log(f"  Back to search. {len(job_indices_new)} Easy Apply jobs remaining.")

    return applied_count


def main():
    global CONFIG

    parser = argparse.ArgumentParser(
        description="LinkedIn Easy Apply Bot - Automatically apply to jobs on LinkedIn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python linkedin_easy_apply_bot.py --profile profiles/my_profile.json
  python linkedin_easy_apply_bot.py --profile profiles/data_engineer_melbourne.json

Create a profile JSON file from one of the examples in the profiles/ folder.
        """,
    )
    parser.add_argument(
        "--profile", "-p",
        required=True,
        help="Path to your JSON profile file (e.g., profiles/my_profile.json)",
    )
    args = parser.parse_args()

    CONFIG = load_config(args.profile)

    log("=" * 60)
    log("LinkedIn Easy Apply Bot")
    log(f"Profile: {args.profile}")
    log(f"Location: {CONFIG['location']}")
    log(f"Keywords: {', '.join(CONFIG['keywords'])}")
    log(f"Max applications: {CONFIG['max_applications']}")
    log("=" * 60)

    driver = create_driver()
    applied_count = 0

    try:
        login(driver)

        for keyword in CONFIG["keywords"]:
            if applied_count >= CONFIG["max_applications"]:
                break
            applied_count = apply_to_jobs(driver, keyword, applied_count)

        log(f"\n{'='*60}")
        log(f"DONE! Applied to {applied_count} jobs.")
        log(f"{'='*60}")

    except KeyboardInterrupt:
        log("\nStopped by user (Ctrl+C).")
    except Exception as e:
        log(f"\nFATAL ERROR: {e}")
        log(traceback.format_exc())
        screenshot(driver, "fatal_error")
    finally:
        log("Done. Browser stays open for 5 minutes, then closes automatically.")
        log("You can close it manually or press Ctrl+C to exit now.")
        try:
            time.sleep(300)
        except KeyboardInterrupt:
            pass
        driver.quit()


if __name__ == "__main__":
    main()
