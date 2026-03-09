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
from selenium.webdriver.common.keys import Keys
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
    cfg.setdefault("search_start", 0)
    cfg.setdefault("cover_letter_text", "")
    cfg.setdefault("default_answer_text", "")
    loc = cfg.get("location", "")
    if "Melbourne" in loc or "Australia" in loc:
        cfg.setdefault("city_for_forms", "Melbourne, Victoria, Australia")
    else:
        cfg.setdefault("city_for_forms", loc.split(",")[0].strip() if loc else "Melbourne, Victoria, Australia")
    cfg.setdefault("relevant_title_keywords", cfg.get("keywords", []))
    cfg.setdefault("max_pages_per_keyword", 10)

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


def js_click_first_apply_button(driver):
    """
    Click the first visible Apply/Easy Apply button via JS.
    Returns button text if clicked, else empty string.
    """
    result = driver.execute_script("""
        var buttons = document.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            if (btn.offsetParent === null) continue;
            var txt = (btn.innerText || btn.textContent || '').trim().toLowerCase();
            var aria = (btn.getAttribute('aria-label') || '').trim().toLowerCase();
            var cls = (btn.className || '').toLowerCase();

            var easyByText = txt.indexOf('easy apply') >= 0;
            var easyByAria = aria.indexOf('easy apply') >= 0;
            var applyByClass = cls.indexOf('jobs-apply-button') >= 0 && (txt.indexOf('apply') >= 0 || aria.indexOf('apply') >= 0);
            var applyByAria = aria.indexOf('apply to') >= 0;

            if (easyByText || easyByAria || applyByClass || applyByAria) {
                btn.scrollIntoView({block: 'center'});
                btn.click();
                return (btn.innerText || btn.textContent || btn.getAttribute('aria-label') || '').trim();
            }
        }
        return '';
    """)
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


def _get_modal_button_texts(driver):
    """Return list of (text, aria-label) for visible buttons in Easy Apply modal."""
    result = driver.execute_script("""
        var container = document.querySelector('.jobs-easy-apply-content') || document.querySelector('.artdeco-modal__content') || document.body;
        var buttons = container.querySelectorAll('button');
        var out = [];
        for (var i = 0; i < buttons.length; i++) {
            var btn = buttons[i];
            if (btn.offsetParent === null) continue;
            var txt = (btn.innerText || btn.textContent || '').trim();
            var aria = (btn.getAttribute('aria-label') || '').trim();
            if (txt || aria) out.push([txt, aria]);
        }
        return out;
    """)
    return result or []


def _has_validation_errors(driver) -> bool:
    """True if modal shows inline validation errors (missing required, etc.)."""
    try:
        errors = driver.find_elements(By.XPATH, "//div[contains(@class,'artdeco-inline-feedback--error')]")
        for e in errors:
            if e.is_displayed() and (e.text or "").strip():
                return True
        return False
    except Exception:
        return False


def _click_modal_button_by_keywords(driver) -> str:
    """
    Find and click the right modal button by searching for keywords.
    Priority: Submit application > Review > Next/Continue.
    Returns the button text clicked, or '' if none matched.
    """
    pairs = _get_modal_button_texts(driver)
    # Decide which action to take by scanning all buttons
    submit_btn = None
    review_btn = None
    next_btn = None
    for (txt, aria) in pairs:
        combined = (f"{txt} {aria}".strip()).lower()
        if "submit application" in combined:
            submit_btn = txt or aria or "Submit application"
        if "review" in combined and not review_btn:
            review_btn = txt or aria or "Review"
        if "next" in combined or "continue to next" in combined:
            next_btn = txt or aria or "Next"
    # Click in priority order
    for candidate in [submit_btn, review_btn, next_btn]:
        if not candidate:
            continue
        if js_find_and_click_button(driver, [candidate]):
            return candidate
    # Fallback: try exact common labels
    for label in ["Submit application", "Review your application", "Review", "Continue to next step", "Next"]:
        if js_find_and_click_button(driver, [label]):
            return label
    return ""


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
    start = int(CONFIG.get("search_start", 0) or 0)
    start_part = f"&start={start}" if start > 0 else ""
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_AL=true&distance={radius}&sortBy=R{start_part}"


def _get_job_cards(driver):
    """Get visible job cards across old/new LinkedIn layouts."""
    selectors = [
        "//li[@data-occludable-job-id]",
        "//li[contains(@class,'jobs-search-results__list-item')]",
        "//div[contains(@class,'job-card-container')]",
    ]
    for xp in selectors:
        cards = driver.find_elements(By.XPATH, xp)
        if cards:
            return cards
    return []


def get_easy_apply_jobs(driver) -> list:
    """
    Return job-card indices to process (skips already-applied).
    In filtered searches (f_AL=true), many cards no longer show the literal
    'Easy Apply' text, so treat visible non-applied cards as valid targets.
    """
    cards = _get_job_cards(driver)
    jobs = []
    for i, card in enumerate(cards):
        try:
            text = (card.text or "").lower()
            if _contains_applied_marker(text):
                continue
            jobs.append(i)
        except StaleElementReferenceException:
            continue
    return jobs


def _get_page_job_records(driver):
    """
    Return job records for current page:
    [{'id': str, 'index': int, 'text': str}, ...]
    """
    cards = _get_job_cards(driver)
    records = []
    for i, card in enumerate(cards):
        try:
            card_text = (card.text or "").strip()
            lower_text = card_text.lower()
            if _contains_applied_marker(lower_text):
                continue

            job_id = (
                card.get_attribute("data-occludable-job-id")
                or card.get_attribute("data-job-id")
                or ""
            ).strip()
            if not job_id:
                try:
                    link = card.find_element(By.XPATH, ".//a[contains(@href,'/jobs/view/')]")
                    href = (link.get_attribute("href") or "").strip()
                    job_id = href or f"idx:{i}:{lower_text[:40]}"
                except Exception:
                    job_id = f"idx:{i}:{lower_text[:40]}"

            records.append({
                "id": job_id,
                "index": i,
                "text": lower_text,
            })
        except StaleElementReferenceException:
            continue
    return records


def click_job_card(driver, index: int):
    """Click on a job card by index."""
    cards = _get_job_cards(driver)
    if index >= len(cards):
        return False
    card = cards[index]
    try:
        link = None
        for xp in [
            ".//a[contains(@class,'job-card-container__link')]",
            ".//a[contains(@class,'job-card-list__title')]",
            ".//a",
        ]:
            try:
                link = card.find_element(By.XPATH, xp)
                break
            except NoSuchElementException:
                continue
        if link is None:
            return False
        js_click(driver, link)
        time.sleep(2)
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


def _contains_applied_marker(text: str) -> bool:
    """True when the card/title indicates this role was already applied."""
    txt = (text or "").lower()
    return "applied" in txt or "see application" in txt


def _is_relevant_title(title: str) -> bool:
    """Only allow titles matching configured relevant role keywords."""
    title_l = (title or "").lower()
    role_keywords = CONFIG.get("relevant_title_keywords") or CONFIG.get("keywords") or []
    role_keywords = [str(k).strip().lower() for k in role_keywords if str(k).strip()]
    if not role_keywords:
        return True
    return any(k in title_l for k in role_keywords)


# ──────────────────────────────────────────────
#  EASY APPLY MODAL
# ──────────────────────────────────────────────

def click_easy_apply_button(driver) -> bool:
    """Find and click the Easy Apply button on the job detail page."""
    xpaths = [
        "//button[contains(@class,'jobs-apply-button') and contains(translate(@aria-label, 'EASYAPPLY', 'easyapply'), 'easy apply')]",
        "//button[contains(@class,'jobs-apply-button') and contains(translate(normalize-space(.), 'EASYAPPLY', 'easyapply'), 'easy apply')]",
        "//button[contains(@class,'jobs-apply-button') and contains(translate(@aria-label, 'APPLY', 'apply'), 'apply')]",
        "//button[contains(@aria-label, 'Easy Apply')]",
        "//button[.//span[contains(text(),'Easy Apply')]]",
        "//button[contains(@aria-label, 'Apply to')]",
    ]
    # Let the job details pane finish rendering the action buttons.
    time.sleep(1)
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            if btn.is_displayed():
                js_click(driver, btn)
                time.sleep(1.5)
                return True
        except (NoSuchElementException, TimeoutException):
            continue

    # JavaScript fallback
    clicked = js_find_and_click_button(driver, ["Easy Apply"])
    if clicked:
        time.sleep(1.5)
        return True
    clicked = js_click_first_apply_button(driver)
    if clicked:
        log(f"  JS clicked apply button: {clicked}")
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


def _is_placeholder_option(opt_text: str) -> bool:
    """True if option looks like a placeholder (Select..., Choose..., --, etc.)."""
    t = (opt_text or "").strip().lower()
    if not t:
        return True
    for p in ["select", "choose", "please select", "select one", "--", "none", "n/a", "select...", "choose..."]:
        if p in t or t == p:
            return True
    return False


def _smart_answer_for_select(label_text: str, options) -> str:
    """Pick the best dropdown option: known question first, else list options and pick first valid."""
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

    # Known: prefer "Yes", then first non-placeholder
    for opt in options:
        if (opt.text or "").strip().lower() == "yes":
            return opt.text.strip()

    # Unknown question: list options and pick first non-placeholder
    opt_texts = [(opt.text or "").strip() for opt in options]
    valid = [t for t in opt_texts if t and not _is_placeholder_option(t)]
    if valid:
        log(f"    Unknown dropdown '{label_text[:50]}' — options: {opt_texts[:10]}{'...' if len(opt_texts) > 10 else ''}; choosing '{valid[0]}'")
        return valid[0]
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


def _try_select_autocomplete_option(inp):
    """
    For combobox/autocomplete fields, choose a dropdown suggestion
    after typing text (common in city/location fields).
    """
    try:
        role = (inp.get_attribute("role") or "").lower()
        aria_auto = (inp.get_attribute("aria-autocomplete") or "").lower()
        controls = (inp.get_attribute("aria-controls") or "").strip()
        has_popup = (inp.get_attribute("aria-haspopup") or "").lower()

        is_autocomplete = (
            role == "combobox"
            or aria_auto in ("list", "both")
            or bool(controls)
            or has_popup in ("listbox", "true")
        )
        if not is_autocomplete:
            return False

        time.sleep(0.3)
        inp.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.15)
        inp.send_keys(Keys.ENTER)
        time.sleep(0.2)
        return True
    except Exception:
        return False


# ──── Form Filling ────

def fill_form_fields(driver) -> bool:
    """Fill all required form fields inside the Easy Apply modal."""
    filled = False
    modal = "//div[contains(@class,'jobs-easy-apply')]"
    years = CONFIG.get("years_of_experience", "5")
    city = CONFIG.get("city_for_forms", "Melbourne, Victoria, Australia")
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
                    if _try_select_autocomplete_option(inp):
                        log("    Selected city/location from dropdown")
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
                # Some LinkedIn text inputs are autocomplete even when label
                # doesn't explicitly include "city/location".
                if _try_select_autocomplete_option(inp):
                    log(f"    Selected dropdown option for '{label_text}'")
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

    # 3) Select dropdowns (<select>)
    try:
        selects = driver.find_elements(By.XPATH, f"{modal}//select")
        for sel in selects:
            try:
                select_obj = Select(sel)
                current = (sel.get_attribute("value") or "").strip()
                if current:
                    continue
                label_text = _get_label(driver, sel)
                options = list(select_obj.options)
                opt_texts = [(o.text or "").strip() for o in options]
                answer = _smart_answer_for_select(label_text, options)
                if answer:
                    select_obj.select_by_visible_text(answer)
                    filled = True
                    log(f"    Selected '{answer}' in dropdown '{label_text}'")
                elif len(options) > 1:
                    # First non-placeholder
                    valid = [t for t in opt_texts if t and not _is_placeholder_option(t)]
                    if valid:
                        select_obj.select_by_visible_text(valid[0])
                        log(f"    Unknown select '{label_text[:40]}' — chose first option: '{valid[0]}'")
                    else:
                        select_obj.select_by_index(1)
                    filled = True
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
    Fills form fields first, checks what's missing (validation errors), then
    searches for keywords (Submit / Review / Next) and clicks the right button.
    """
    max_steps = 25
    stuck_count = 0

    for step in range(max_steps):
        log(f"  Step {step + 1}/{max_steps}")

        js_scroll_modal(driver)
        current_progress = _get_modal_progress(driver)

        # Fill form fields first
        filled = fill_form_fields(driver)
        if filled:
            js_scroll_modal(driver)
            time.sleep(0.3)

        # If validation errors are shown, don't click Next — something is missing
        if _has_validation_errors(driver):
            log("    Validation errors present — not clicking Next until fixed")
            stuck_count += 1
            if stuck_count >= 3:
                log("    Still errors after 3 passes. Taking screenshot and giving up.")
                screenshot(driver, f"step{step+1}_validation_errors")
                break
            continue
        stuck_count = 0

        # Search for Submit / Review / Next by keyword and click the right one
        clicked = _click_modal_button_by_keywords(driver)
        if not clicked:
            log("    No Submit/Review/Next button found. Breaking.")
            screenshot(driver, f"step{step+1}_no_button")
            break

        log(f"    -> Clicked '{clicked}'")
        time.sleep(1 if "Submit" not in clicked else 1.5)

        if "submit" in clicked.lower():
            _handle_post_submit(driver)
            return True

        new_progress = _get_modal_progress(driver)
        if new_progress and new_progress == current_progress:
            stuck_count += 1
            log(f"    Progress unchanged ({new_progress}). Stuck count: {stuck_count}")
            if stuck_count >= 3:
                log("    Stuck for 3 attempts. Giving up.")
                screenshot(driver, f"step{step+1}_stuck")
                break
        else:
            stuck_count = 0

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


def _go_to_next_results_page(driver) -> bool:
    """Click the next page button in LinkedIn job search results."""
    next_xpaths = [
        "//button[@aria-label='View next page']",
        "//button[contains(@aria-label,'next page')]",
        "//button[contains(@aria-label,'Next')]",
    ]
    for xp in next_xpaths:
        try:
            btn = driver.find_element(By.XPATH, xp)
            if btn.is_displayed() and btn.is_enabled():
                js_click(driver, btn)
                time.sleep(2)
                return True
        except NoSuchElementException:
            continue
        except Exception:
            continue
    return False


# ──────────────────────────────────────────────
#  MAIN APPLICATION LOOP
# ──────────────────────────────────────────────

def apply_to_jobs(driver, keyword: str, applied_count: int) -> int:
    """Search for jobs with a keyword and apply. Returns updated count."""
    location = CONFIG["location"]
    max_apps = CONFIG.get("max_applications", 50)
    max_pages = int(CONFIG.get("max_pages_per_keyword", 10))
    url = build_search_url(keyword, location)

    log(f"\n{'='*60}")
    log(f"Searching: '{keyword}' in {location}")
    log(f"{'='*60}")
    driver.get(url)
    time.sleep(2)

    _ensure_easy_apply_filter(driver)
    time.sleep(1)

    for page_num in range(1, max_pages + 1):
        log(f"Processing results page {page_num}/{max_pages}")
        current_results_url = driver.current_url
        processed_ids = set()
        no_progress_passes = 0
        while True:
            if applied_count >= max_apps:
                log(f"Reached max applications ({max_apps}). Stopping.")
                return applied_count

            page_records = _get_page_job_records(driver)
            if not page_records:
                log("Found 0 Easy Apply jobs on this page")
                break

            pending = [r for r in page_records if r["id"] not in processed_ids]
            if not pending:
                log("No unprocessed Easy Apply jobs left on this page.")
                break

            if no_progress_passes == 0:
                log(f"Found {len(page_records)} Easy Apply jobs on this page")
            log(f"Pending jobs on this page: {len(pending)}")

            before_attempt_count = applied_count
            for rec in pending:
                processed_ids.add(rec["id"])
                idx = rec["index"]
                if not click_job_card(driver, idx):
                    continue

                title = get_job_title(driver)
                log(f"\nJob #{applied_count + 1}: {title}")
                if _contains_applied_marker(title):
                    log("  Skipping: already applied role.")
                    continue
                if not _is_relevant_title(title):
                    log("  Skipping: non-data role based on title keywords.")
                    continue

                if not click_easy_apply_button(driver):
                    log("  No Easy Apply button found. Skipping.")
                    continue

                success = process_easy_apply_modal(driver)
                if success:
                    applied_count += 1
                    log(f"  *** APPLIED SUCCESSFULLY *** (Total: {applied_count})")
                else:
                    log("  Could not complete application. Skipping.")

                # Return to same results page and continue processing pending jobs.
                driver.get(current_results_url)
                time.sleep(2)
                _ensure_easy_apply_filter(driver)
                time.sleep(1)

                if applied_count >= max_apps:
                    log(f"Reached max applications ({max_apps}). Stopping.")
                    return applied_count

            if applied_count == before_attempt_count:
                no_progress_passes += 1
            else:
                no_progress_passes = 0

            if no_progress_passes >= 2:
                log("No progress after 2 passes on this page. Moving to next page.")
                break

        if page_num >= max_pages:
            log("Reached max pages per keyword.")
            break
        if not _go_to_next_results_page(driver):
            log("No next page available. Stopping pagination for this keyword.")
            break
        _ensure_easy_apply_filter(driver)
        time.sleep(1)

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
