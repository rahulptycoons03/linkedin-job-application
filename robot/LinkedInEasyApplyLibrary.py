"""Robot Framework library for LinkedIn Easy Apply (Australia Data Engineer)."""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import List

from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "logs", "screenshots")


def _driver():
    return BuiltIn().get_library_instance("SeleniumLibrary").driver


def _wait(timeout=10):
    return WebDriverWait(_driver(), timeout)


def _screenshot(driver, label: str = "debug") -> None:
    """Save a screenshot for debugging."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"robot_{label}_{ts}.png")
        driver.save_screenshot(path)
        logger.info(f"Screenshot saved: {path}")
    except Exception as e:
        logger.warn(f"Could not save screenshot: {e}")


def _log_page_buttons(driver, context: str = "") -> None:
    """Log all visible buttons on page for debugging."""
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        visible_btns = []
        for b in buttons:
            try:
                if b.is_displayed():
                    text = (b.text or "").strip()[:60]
                    aria = (b.get_attribute("aria-label") or "").strip()[:60]
                    classes = (b.get_attribute("class") or "").strip()[:80]
                    if text or aria:
                        visible_btns.append(f"  text='{text}' aria='{aria}' class='{classes}'")
            except StaleElementReferenceException:
                continue
        if visible_btns:
            logger.info(f"[{context}] Visible buttons ({len(visible_btns)}):\n" + "\n".join(visible_btns[:20]))
        else:
            logger.warn(f"[{context}] No visible buttons found on page!")
    except Exception as e:
        logger.warn(f"Could not log buttons: {e}")


def get_easy_apply_card_indices() -> List[int]:
    """Return 0-based indices of job cards that show Easy Apply and not Applied."""
    driver = _driver()
    cards = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
    indices = []
    for i, card in enumerate(cards):
        try:
            text = (card.text or "").lower()
            if "applied" in text or "see application" in text:
                continue
            if "easy apply" in text:
                indices.append(i)
        except Exception:
            continue
    return indices


def click_job_card_by_index(index: int) -> None:
    """Click the job card at the given index (0-based)."""
    driver = _driver()
    cards = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")
    if index >= len(cards):
        raise ValueError(f"Job card index {index} out of range (max {len(cards) - 1})")
    card = cards[index]
    try:
        link = card.find_element(By.TAG_NAME, "a")
    except NoSuchElementException:
        raise
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
    time.sleep(0.5)
    try:
        link.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", link)
    time.sleep(2)


def easy_apply_button_present() -> bool:
    """True if the main apply control is Easy Apply (not external)."""
    driver = _driver()
    selectors = [
        "//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]",
        "//button[contains(@aria-label, 'Easy Apply')]",
        "//button[.//span[contains(text(),'Easy Apply')]]",
    ]
    for xp in selectors:
        try:
            el = driver.find_element(By.XPATH, xp)
            return el.is_displayed()
        except NoSuchElementException:
            continue
    return False


def _js_click_button(driver, button_texts: List[str]) -> str:
    """Use JavaScript to find a button by its span/text content and click it. Returns the matched text or empty string."""
    try:
        result = driver.execute_script("""
            var texts = arguments[0];
            var allButtons = document.querySelectorAll('button');
            for (var t = 0; t < texts.length; t++) {
                for (var i = 0; i < allButtons.length; i++) {
                    var btn = allButtons[i];
                    var span = btn.querySelector('span');
                    var btnText = (span ? span.textContent : btn.textContent).trim();
                    if (btnText === texts[t]) {
                        btn.scrollIntoView({block: 'center'});
                        btn.click();
                        return texts[t];
                    }
                }
            }
            return '';
        """, button_texts)
        return result or ""
    except Exception as e:
        logger.warn(f"JS click button failed: {e}")
        return ""


def _scroll_modal_down(driver) -> None:
    """Scroll down inside the Easy Apply modal to reveal buttons below the fold."""
    try:
        # Find the scrollable container inside the Easy Apply modal
        modal_containers = [
            "//div[contains(@class,'jobs-easy-apply-modal')]//div[contains(@class,'jobs-easy-apply-content')]",
            "//div[contains(@class,'jobs-easy-apply-modal')]//div[contains(@class,'artdeco-modal__content')]",
            "//div[contains(@class,'artdeco-modal__content')]",
            "//div[contains(@class,'jobs-easy-apply')]",
        ]
        for xp in modal_containers:
            try:
                container = driver.find_element(By.XPATH, xp)
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
                time.sleep(0.5)
                return
            except NoSuchElementException:
                continue
        # Fallback: scroll the whole page down a bit
        driver.execute_script("window.scrollBy(0, 300);")
        time.sleep(0.3)
    except Exception as e:
        logger.warn(f"Could not scroll modal: {e}")


def _click_btn(driver, xpaths: List[str]) -> bool:
    for xp in xpaths:
        try:
            el = driver.find_element(By.XPATH, xp)
            # Scroll element into view first, even if not currently visible
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            time.sleep(0.3)
            if not el.is_enabled():
                continue
            try:
                el.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", el)
            return True
        except NoSuchElementException:
            continue
    return False


def _fill_form_fields(driver) -> bool:
    """Fill empty required form fields in the Easy Apply modal. Returns True if anything was filled."""
    filled = False

    # 1. Fill empty required text/number inputs (e.g. years of experience, city)
    try:
        inputs = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'jobs-easy-apply')]//input[@required and (@type='text' or @type='number' or not(@type))]",
        )
        for inp in inputs:
            try:
                if not (inp.get_attribute("value") or "").strip():
                    label_text = ""
                    try:
                        label_id = inp.get_attribute("id")
                        if label_id:
                            label_el = driver.find_element(By.XPATH, f"//label[@for='{label_id}']")
                            label_text = (label_el.text or "").lower()
                    except Exception:
                        pass
                    inp.clear()
                    if "year" in label_text or "experience" in label_text:
                        inp.send_keys("5")
                    elif "city" in label_text or "location" in label_text:
                        inp.send_keys("Melbourne")
                    elif "salary" in label_text or "pay" in label_text or "rate" in label_text:
                        inp.send_keys("120000")
                    elif "phone" in label_text or "mobile" in label_text:
                        inp.send_keys("0400000000")
                    else:
                        inp.send_keys("5")
                    filled = True
                    time.sleep(0.3)
            except Exception:
                continue
    except Exception:
        pass

    # 2. Fill empty required textareas
    try:
        textareas = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'jobs-easy-apply')]//textarea[@required]",
        )
        for ta in textareas:
            try:
                if not (ta.get_attribute("value") or "").strip():
                    ta.clear()
                    ta.send_keys("I have extensive experience in this area and am keen to contribute to your team.")
                    filled = True
                    time.sleep(0.3)
            except Exception:
                continue
    except Exception:
        pass

    # 3. Handle required select dropdowns that haven't been selected
    try:
        selects = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'jobs-easy-apply')]//select[@required]",
        )
        for sel in selects:
            try:
                from selenium.webdriver.support.ui import Select
                select = Select(sel)
                current_val = sel.get_attribute("value") or ""
                if not current_val or current_val == "":
                    options = select.options
                    # Pick the first non-placeholder option (often index 1)
                    for opt in options:
                        val = opt.get_attribute("value") or ""
                        text = (opt.text or "").strip().lower()
                        if val and text and text != "select an option" and text != "select" and text != "--":
                            # Prefer "Yes" if available
                            pass
                        continue
                    # Try to select "Yes" first
                    yes_found = False
                    for opt in options:
                        if (opt.text or "").strip().lower() == "yes":
                            select.select_by_visible_text(opt.text.strip())
                            yes_found = True
                            filled = True
                            break
                    if not yes_found and len(options) > 1:
                        select.select_by_index(1)
                        filled = True
                    time.sleep(0.3)
            except Exception:
                continue
    except Exception:
        pass

    # 4. Handle radio buttons (pick first option or "Yes")
    try:
        fieldsets = driver.find_elements(
            By.XPATH,
            "//div[contains(@class,'jobs-easy-apply')]//fieldset[.//input[@type='radio']]",
        )
        for fs in fieldsets:
            try:
                radios = fs.find_elements(By.XPATH, ".//input[@type='radio']")
                any_checked = any(r.is_selected() for r in radios)
                if not any_checked and radios:
                    # Try "Yes" first
                    clicked = False
                    for r in radios:
                        try:
                            label = r.find_element(By.XPATH, "./following-sibling::label | ../label")
                            if "yes" in (label.text or "").lower():
                                driver.execute_script("arguments[0].click();", r)
                                clicked = True
                                filled = True
                                break
                        except Exception:
                            continue
                    if not clicked:
                        driver.execute_script("arguments[0].click();", radios[0])
                        filled = True
                    time.sleep(0.3)
            except Exception:
                continue
    except Exception:
        pass

    return filled


def try_easy_apply_and_submit() -> bool:
    """
    Click Easy Apply, then loop: Next / Continue / Review -> click; fill required fields if needed;
    Submit application -> click; Done -> click. Return True if submitted.
    """
    driver = _driver()
    for xp in [
        "//button[contains(@class,'jobs-apply-button') and contains(@aria-label, 'Easy')]",
        "//button[contains(@aria-label, 'Easy Apply')]",
        "//button[.//span[contains(text(),'Easy Apply')]]",
    ]:
        try:
            btn = driver.find_element(By.XPATH, xp)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
            try:
                btn.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", btn)
            logger.info("Clicked Easy Apply button.")
            break
        except NoSuchElementException:
            continue
    else:
        logger.warn("Could not find Easy Apply button to click.")
        return False

    time.sleep(3)
    _screenshot(driver, "after_easy_apply_click")
    _log_page_buttons(driver, "after_easy_apply_click")

    submitted = False
    max_steps = 25

    submit_xpaths = [
        "//button[contains(., 'Submit application')]",
        "//button[@aria-label='Submit application']",
    ]
    continue_xpaths = [
        "//button[@aria-label='Continue to next step']",
        "//button[contains(., 'Continue to next step')]",
        "//button[@aria-label='Review your application']",
        "//button[contains(., 'Review your application')]",
        "//button[contains(@aria-label, 'next')]",
        "//button[contains(@aria-label, 'Next')]",
        "//button[span[text()='Next']]",
        "//button[contains(., 'Next')]",
        "//button[span[contains(text(),'Next')]]",
        "//footer//button[contains(@class,'artdeco-button--primary')]",
        "//div[contains(@class,'jobs-easy-apply')]//button[contains(@class,'artdeco-button--primary')]",
    ]

    for step in range(max_steps):
        logger.info(f"Easy Apply modal step {step + 1}/{max_steps}")

        # Scroll down inside the modal to reveal buttons below the fold
        _scroll_modal_down(driver)

        # Check for Submit application button first
        if _click_btn(driver, submit_xpaths):
            logger.info("Clicked 'Submit application'.")
            submitted = True
            time.sleep(3)
            break

        # Check for Next / Continue / Review buttons
        if _click_btn(driver, continue_xpaths):
            logger.info(f"Clicked next/continue button at step {step + 1}.")
            time.sleep(2)
            continue

        # Buttons not found yet - scroll modal down further and retry
        logger.info(f"Buttons not visible at step {step + 1}, scrolling modal down and retrying...")
        _scroll_modal_down(driver)
        time.sleep(0.5)

        if _click_btn(driver, submit_xpaths):
            logger.info("Clicked 'Submit application' after scroll.")
            submitted = True
            time.sleep(3)
            break

        if _click_btn(driver, continue_xpaths):
            logger.info(f"Clicked next/continue after scroll at step {step + 1}.")
            time.sleep(2)
            continue

        # JavaScript fallback: find button by span text content and click it
        js_clicked = _js_click_button(driver, ["Next", "Continue to next step", "Review your application", "Submit application"])
        if js_clicked:
            clicked_text = js_clicked
            logger.info(f"JS fallback clicked '{clicked_text}' at step {step + 1}.")
            if "submit" in clicked_text.lower():
                submitted = True
                time.sleep(3)
                break
            time.sleep(2)
            continue

        # Try filling form fields, then scroll and retry clicking next
        logger.info(f"No button found at step {step + 1}. Trying to fill form fields...")
        _screenshot(driver, f"step_{step+1}_stuck")

        if _fill_form_fields(driver):
            logger.info(f"Filled form fields at step {step + 1}, scrolling down and retrying next button.")
            time.sleep(1)
            _scroll_modal_down(driver)
            time.sleep(0.5)
            if _click_btn(driver, continue_xpaths):
                logger.info(f"Clicked next/continue after filling fields at step {step + 1}.")
                time.sleep(2)
                continue
            if _click_btn(driver, submit_xpaths):
                logger.info("Clicked 'Submit application' after filling fields.")
                submitted = True
                time.sleep(3)
                break

        # Check if a dismiss/close/discard dialog appeared (e.g. unsaved changes)
        try:
            discard_btn = driver.find_element(By.XPATH, "//button[contains(., 'Discard')]")
            if discard_btn.is_displayed():
                logger.warn("Discard dialog detected, clicking Discard.")
                discard_btn.click()
                time.sleep(1)
                break
        except NoSuchElementException:
            pass

        logger.warn(f"No actionable button found at step {step + 1}, breaking.")
        _screenshot(driver, f"step_{step+1}_no_action")
        break

    if submitted:
        try:
            done = _wait(5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Done')]"))
            )
            try:
                done.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", done)
            logger.info("Clicked 'Done' after submission.")
            time.sleep(2)
        except TimeoutException:
            try:
                driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']").click()
                logger.info("Clicked 'Dismiss' after submission.")
            except NoSuchElementException:
                pass
    else:
        # Close modal if still open
        logger.warn("Application not submitted. Attempting to close modal.")
        try:
            close_btn = driver.find_element(By.XPATH, "//button[@aria-label='Dismiss']")
            close_btn.click()
            time.sleep(1)
            try:
                discard_btn = driver.find_element(By.XPATH, "//button[contains(., 'Discard')]")
                discard_btn.click()
                time.sleep(1)
            except NoSuchElementException:
                pass
        except NoSuchElementException:
            pass

    return submitted


def go_back_to_search(search_url: str) -> None:
    """Navigate back to the search results page."""
    _driver().get(search_url)
    time.sleep(2)


def build_search_url(keywords: str, location: str) -> str:
    """Build LinkedIn jobs search URL with Easy Apply filter."""
    from urllib.parse import quote_plus
    kw = quote_plus(keywords)
    loc = quote_plus(location)
    return f"https://www.linkedin.com/jobs/search/?keywords={kw}&location={loc}&f_AL=true&sortBy=R"
