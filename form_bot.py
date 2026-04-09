"""
Google Form filler: Selenium + Chrome profile reuse, constants-based answers,
optional ChatGPT (web UI in a new tab, no API key).
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

import pyautogui
import pyperclip

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

log = logging.getLogger("form_bot")

pyautogui.FAILSAFE = True

SECTION_SELECTORS = [
    "div.Qr7Oae",
    "div[data-params]",
    "div.freebirdFormviewerViewItemsItemItem",
]

# -------------------------------
# Resume + input helpers
# -------------------------------

def load_resume_text(resume_path: Path, max_chars: int = 12000) -> str:
    if not resume_path.is_file():
        return f"(No resume file at {resume_path})"
    suf = resume_path.suffix.lower()
    if suf == ".txt":
        return resume_path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    if suf == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(resume_path))
        parts: list[str] = []
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t)
            if sum(len(p) for p in parts) >= max_chars:
                break
        return "\n".join(parts)[:max_chars]
    return f"(Unsupported resume type {suf}; use .pdf or .txt.)"

def match_mapping(question: str, mapping: dict[str, str]) -> str | None:
    q = question.lower()
    for key, val in mapping.items():
        k = (key or "").strip().lower()
        if len(k) < 2:
            continue
        if k in q:
            return val
    return None

def section_question_text(section: WebElement) -> str:
    for sel in (
        '[role="heading"]',
        "span.M7eMe",
        "div.M7eMe",
        ".HoXoMd",
        "span.aG9Vid",
    ):
        try:
            els = section.find_elements(By.CSS_SELECTOR, sel)
            if els:
                t = els[0].text.strip()
                if len(t) > 2:
                    return t
        except Exception:
            pass
    raw = section.text.strip()
    line = next((ln.strip() for ln in raw.splitlines() if len(ln.strip()) > 2), raw)
    return line[:500]

def iter_sections(driver: webdriver.Chrome):
    for css in SECTION_SELECTORS:
        els = driver.find_elements(By.CSS_SELECTOR, css)
        if els:
            log.info("Using section selector %s (%d blocks)", css, len(els))
            for el in els:
                yield el
            return
    log.warning(
        "No known section selector matched. Add a selector to SECTION_SELECTORS in form_bot.py."
    )

# -------------------------------
# File upload (Add file → screen templates → Browse → native dialog)
# -------------------------------
def wait_for_screen_image(path: Path, timeout_sec: float, confidence: float, poll: float = 0.45) -> bool:
    """Return True when template image is visible on screen (requires opencv for confidence)."""
    p = str(path.resolve())
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            box = pyautogui.locateOnScreen(p, confidence=confidence)
            if box:
                return True
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            log.debug("locateOnScreen: %s", e)
        time.sleep(poll)
    return False


def screen_image_visible(path: Path, confidence: float) -> bool:
    """True if template matches current screen (OpenCV confidence)."""
    p = str(path.resolve())
    try:
        box = pyautogui.locateOnScreen(p, confidence=confidence)
        return box is not None
    except pyautogui.ImageNotFoundException:
        return False
    except Exception as e:
        log.debug("screen_image_visible: %s", e)
        return False


def click_screen_image(path: Path, confidence: float) -> bool:
    p = str(path.resolve())
    try:
        box = pyautogui.locateOnScreen(p, confidence=confidence)
        if not box:
            return False
        pt = pyautogui.center(box)
        pyautogui.click(pt.x, pt.y)
        return True
    except pyautogui.ImageNotFoundException:
        return False
    except Exception as e:
        log.debug("click_screen_image: %s", e)
        return False


def wait_and_click_screen_image(
    path: Path, timeout_sec: float, confidence: float, poll: float = 0.45
) -> bool:
    """Poll until template appears, then click its center (OpenCV confidence)."""
    p = str(path.resolve())
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            box = pyautogui.locateOnScreen(p, confidence=confidence)
            if box:
                pt = pyautogui.center(box)
                pyautogui.click(pt.x, pt.y)
                return True
        except pyautogui.ImageNotFoundException:
            pass
        except Exception as e:
            log.debug("wait_and_click_screen_image: %s", e)
        time.sleep(poll)
    return False


def section_has_add_file(section: WebElement) -> bool:
    try:
        els = section.find_elements(
            By.XPATH,
            ".//*[contains(translate(., 'ADDFILE', 'addfile'), 'add file')]",
        )
        return any(e.is_displayed() for e in els)
    except Exception:
        return False


def click_add_file_in_section(section: WebElement) -> bool:
    xpaths = [
        ".//*[self::div or self::span][contains(translate(., 'ADDFILE', 'addfile'), 'add file')]",
        ".//div[contains(., 'Add file')]",
        ".//span[contains(., 'Add file')]",
        ".//*[contains(., 'Add file')]",
    ]
    for xp in xpaths:
        for el in section.find_elements(By.XPATH, xp):
            try:
                if el.is_displayed() and el.is_enabled():
                    el.click()
                    return True
            except Exception:
                continue
    return False


def submit_native_file_dialog(resume_path: Path) -> bool:
    path_str = str(resume_path.resolve())
    try:
        pyperclip.copy(path_str)
    except Exception as e:
        log.exception("Clipboard copy failed: %s", e)
        return False
    time.sleep(0.25)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.35)
    pyautogui.press("enter")
    time.sleep(0.4)
    log.info("Pasted path into native file dialog and pressed Enter")
    return True


def finalize_upload_after_paste(
    insert_file_image: Path,
    browse_button_image: Path,
    resume_path: Path,
    image_confidence: float,
    *,
    poll_sec: float,
    loading_timeout_sec: float,
    max_browse_retries: int,
) -> bool:
    """
    After path + Enter in the native file dialog:
    - insert + browse visible → treat as failed pick; retry Browse + path (bounded).
    - insert visible, browse not → loading; wait until insert disappears or timeout.
    - insert not visible → uploaded; continue form.
    """
    browse_retries = 0

    def retry_browse_and_paste() -> bool:
        nonlocal browse_retries
        if browse_retries >= max_browse_retries:
            log.error("Max Browse retries reached (%s)", max_browse_retries)
            return False
        browse_retries += 1
        log.warning(
            "Retrying Browse + file path (%s / %s)",
            browse_retries,
            max_browse_retries,
        )
        if not click_screen_image(browse_button_image, image_confidence):
            log.error("Retry: could not click Browse image")
            return False
        time.sleep(0.85)
        return submit_native_file_dialog(resume_path)

    time.sleep(0.55)

    while True:
        insert_vis = screen_image_visible(insert_file_image, image_confidence)
        browse_vis = screen_image_visible(browse_button_image, image_confidence)

        if not insert_vis:
            log.info("Insert-file UI gone — file upload step finished")
            return True

        if insert_vis and browse_vis:
            log.warning(
                "Insert + Browse both visible — file likely did not upload; retry from Browse"
            )
            if not retry_browse_and_paste():
                return False
            time.sleep(0.55)
            continue

        # Insert visible, Browse not → uploading / loading
        log.info("Insert UI without Browse — waiting for upload to complete…")
        deadline = time.time() + loading_timeout_sec
        while time.time() < deadline:
            time.sleep(poll_sec)
            insert_vis = screen_image_visible(insert_file_image, image_confidence)
            browse_vis = screen_image_visible(browse_button_image, image_confidence)
            if not insert_vis:
                log.info("Insert UI cleared after load — upload complete")
                return True
            if insert_vis and browse_vis:
                log.warning(
                    "Insert + Browse visible again during wait — retry from Browse"
                )
                if not retry_browse_and_paste():
                    return False
                time.sleep(0.55)
                break
        else:
            log.error("Timeout while waiting for upload (insert UI did not clear)")
            return False
        continue


def upload_via_iframe(driver: webdriver.Chrome, resume_path: Path) -> bool:
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    if not iframes:
        log.warning("No iframe found for file upload fallback")
        return False
    for frame in iframes:
        try:
            driver.switch_to.frame(frame)
            file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
            if file_inputs:
                file_inputs[0].send_keys(str(resume_path.resolve()))
                log.info("Uploaded resume inside iframe (fallback)")
                time.sleep(2)
                driver.switch_to.default_content()
                return True
            driver.switch_to.default_content()
        except Exception:
            driver.switch_to.default_content()
            continue
    log.warning("No file input found inside any iframe")
    return False


def upload_resume_google_form(
    driver: webdriver.Chrome,
    resume_path: Path,
    section: WebElement,
    *,
    headed: bool,
    add_file_button_image: Path | None,
    insert_file_image: Path | None,
    browse_button_image: Path | None,
    image_confidence: float,
    image_wait_timeout: float,
    upload_poll_sec: float,
    upload_loading_timeout_sec: float,
    upload_max_browse_retries: int,
) -> bool:
    driver.switch_to.default_content()
    try:
        if not resume_path.is_file():
            log.error("Resume file not found: %s", resume_path)
            return False

        use_images = (
            headed
            and insert_file_image is not None
            and browse_button_image is not None
            and insert_file_image.is_file()
            and browse_button_image.is_file()
        )
        use_add_file_image = (
            use_images
            and add_file_button_image is not None
            and add_file_button_image.is_file()
        )
        if not use_images:
            if headed and (insert_file_image or browse_button_image):
                miss = []
                if insert_file_image and not insert_file_image.is_file():
                    miss.append(str(insert_file_image))
                if browse_button_image and not browse_button_image.is_file():
                    miss.append(str(browse_button_image))
                if miss:
                    log.warning("Image file(s) missing, using iframe fallback: %s", miss)
            elif not headed and insert_file_image and browse_button_image:
                log.warning("Headless mode: image upload disabled; using iframe fallback if possible.")

        if use_add_file_image:
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                    section,
                )
            except Exception:
                pass
            time.sleep(0.5)
            log.info("Waiting for Add file control image: %s", add_file_button_image.name)
            if not wait_and_click_screen_image(
                add_file_button_image, image_wait_timeout, image_confidence
            ):
                log.error("Timeout: Add file image not found (%s)", add_file_button_image)
                return False
            log.info("Clicked Add file via image match")
            time.sleep(1.0)
        else:
            if not click_add_file_in_section(section):
                log.warning("Could not find/click Add file in this section")
                return False
            time.sleep(1.0)

        if use_images:
            log.info("Waiting for insert-file UI image: %s", insert_file_image.name)
            if not wait_for_screen_image(insert_file_image, image_wait_timeout, image_confidence):
                log.error("Timeout: insert file UI not detected (%s)", insert_file_image)
                return False
            log.info("Insert-file UI matched on screen")
            time.sleep(0.35)
            log.info("Looking for Browse control image: %s", browse_button_image.name)
            if not click_screen_image(browse_button_image, image_confidence):
                log.error("Browse button image not found on screen (%s)", browse_button_image)
                return False
            time.sleep(0.9)
            if not submit_native_file_dialog(resume_path):
                return False
            return finalize_upload_after_paste(
                insert_file_image,
                browse_button_image,
                resume_path,
                image_confidence,
                poll_sec=upload_poll_sec,
                loading_timeout_sec=upload_loading_timeout_sec,
                max_browse_retries=upload_max_browse_retries,
            )

        time.sleep(1.0)
        return upload_via_iframe(driver, resume_path)

    except Exception as e:
        log.exception("Upload failed: %s", e)
        driver.switch_to.default_content()
        return False

# -------------------------------
# Text / radio helpers
# -------------------------------
def _section_driver(section: WebElement):
    return getattr(section, "_parent", None)


def fill_text_in_section(section: WebElement, text: str) -> bool:
    """Google Forms often uses contenteditable divs; plain input/textarea also supported."""
    driver = _section_driver(section)
    if driver:
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',inline:'nearest'});",
                section,
            )
        except Exception:
            pass
    time.sleep(0.15)

    candidates: list[WebElement] = []
    for sel in (
        'div[contenteditable="true"]',
        '[role="textbox"]',
        "textarea",
        'input[type="text"]',
        'input:not([type="hidden"])',
    ):
        try:
            for el in section.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    candidates.append(el)
        except Exception:
            continue

    if not candidates:
        return False

    el = candidates[0]
    try:
        tag = (el.tag_name or "").lower()
        editable = (el.get_attribute("contenteditable") or "").lower() == "true"

        if tag in ("textarea", "input"):
            el.click()
            time.sleep(0.05)
            try:
                el.clear()
            except Exception:
                el.send_keys(Keys.CONTROL, "a")
                el.send_keys(Keys.BACKSPACE)
            el.send_keys(text)
            return True

        if editable or el.get_attribute("role") == "textbox":
            el.click()
            time.sleep(0.12)
            if driver:
                try:
                    driver.execute_script(
                        """
                        var el = arguments[0], t = arguments[1];
                        el.focus();
                        if (el.isContentEditable) {
                          el.innerText = t;
                          el.dispatchEvent(new Event('input', {bubbles: true}));
                          el.dispatchEvent(new Event('change', {bubbles: true}));
                        }
                        """,
                        el,
                        text,
                    )
                    return True
                except Exception:
                    pass
                ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(
                    Keys.CONTROL
                ).send_keys(Keys.BACKSPACE).send_keys(text).perform()
            else:
                el.send_keys(Keys.CONTROL, "a")
                el.send_keys(Keys.BACKSPACE)
                el.send_keys(text)
            return True
    except Exception as e:
        log.debug("fill_text_in_section primary: %s", e)

    if driver:
        try:
            driver.execute_script(
                """
                var el = arguments[0], t = arguments[1];
                el.scrollIntoView({block:'center'});
                el.focus();
                if (el.isContentEditable) { el.innerText = t; }
                else if (el.value !== undefined) { el.value = t; }
                el.dispatchEvent(new Event('input', {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
                """,
                el,
                text,
            )
            return True
        except Exception as e:
            log.debug("fill_text_in_section JS fallback: %s", e)
    return False

def click_radio_by_label(section: WebElement, label_substring: str) -> bool:
    sub = label_substring.lower()
    try:
        radios = section.find_elements(By.CSS_SELECTOR, '[role="radio"], input[type="radio"]')
        for r in radios:
            aria = (r.get_attribute("aria-label") or "") + (r.get_attribute("name") or "")
            if sub in aria.lower():
                r.click()
                return True
        for el in section.find_elements(By.XPATH, ".//*"):
            try:
                t = (el.text or "").strip()
                if t and sub in t.lower() and el.is_displayed():
                    el.click()
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False

# -------------------------------
# ChatGPT (web UI, new tab — same Chrome session / profile, no API key)
# -------------------------------
def _open_new_tab(driver: webdriver.Chrome) -> None:
    try:
        driver.switch_to.new_window("tab")
    except Exception:
        driver.execute_script("window.open('about:blank','_blank');")
        time.sleep(0.4)
        handles = driver.window_handles
        driver.switch_to.window(handles[-1])


def ask_chatgpt_via_browser(
    driver: webdriver.Chrome,
    question: str,
    resume_excerpt: str,
    *,
    headed: bool,
    chatgpt_url: str,
    response_timeout_sec: float,
    prompt_wait_sec: float,
    max_resume_chars: int,
) -> str:
    """
    Opens ChatGPT in a new tab, pastes question + resume, reads the last assistant reply.
    Requires: visible browser, ChatGPT logged in on this Chrome profile.
    """
    if not headed:
        log.warning("ChatGPT web step skipped (headless mode)")
        return ""

    form_handle = driver.current_window_handle
    resume_excerpt = (resume_excerpt or "")[:max_resume_chars]
    question = (question or "")[:3000]
    body = (
        "Answer this job-application form question using ONLY information from the resume below. "
        "If the resume does not support an answer, say so in one short sentence. "
        "Reply with plain text for a single form field only — no quotes, no markdown, "
        "no line like 'Answer:'.\n\n"
        f"Question:\n{question}\n\n"
        f"Resume:\n{resume_excerpt}"
    )

    try:
        _open_new_tab(driver)
        driver.get((chatgpt_url or "https://chatgpt.com").strip())
        time.sleep(2.5)

        wait = WebDriverWait(driver, prompt_wait_sec)
        prompt_el = None
        for by, sel in (
            (By.CSS_SELECTOR, "#prompt-textarea"),
            (By.CSS_SELECTOR, "textarea[data-id]"),
            (By.CSS_SELECTOR, "div#prompt-textarea"),
            (By.CSS_SELECTOR, "div[contenteditable='true'][data-id]"),
            (By.CSS_SELECTOR, "div[contenteditable='true']"),
        ):
            try:
                el = wait.until(EC.presence_of_element_located((by, sel)))
                if el.is_displayed():
                    prompt_el = el
                    break
            except Exception:
                continue

        if not prompt_el:
            log.error(
                "ChatGPT: could not find the message box (log in at %s in this profile first)",
                chatgpt_url,
            )
            driver.close()
            driver.switch_to.window(form_handle)
            return ""

        try:
            pyperclip.copy(body)
        except Exception as e:
            log.exception("Clipboard failed for ChatGPT prompt: %s", e)
            driver.close()
            driver.switch_to.window(form_handle)
            return ""

        prompt_el.click()
        time.sleep(0.2)
        try:
            prompt_el.send_keys(Keys.CONTROL, "a")
            prompt_el.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        prompt_el.send_keys(Keys.CONTROL, "v")
        time.sleep(0.4)

        sent = False
        for by, sel in (
            (By.CSS_SELECTOR, 'button[data-testid="send-button"]'),
            (By.CSS_SELECTOR, 'button[data-testid*="send"]'),
            (By.CSS_SELECTOR, "button[aria-label*='Send']"),
        ):
            try:
                btn = driver.find_element(by, sel)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    sent = True
                    break
            except Exception:
                continue
        if not sent:
            prompt_el.send_keys(Keys.ENTER)

        log.info("ChatGPT tab: waiting for reply (timeout %ss)…", int(response_timeout_sec))
        deadline = time.time() + response_timeout_sec
        last_assistant = ""
        stable_rounds = 0
        while time.time() < deadline:
            time.sleep(2.0)
            try:
                stop_btns = driver.find_elements(
                    By.CSS_SELECTOR,
                    'button[aria-label*="Stop"], button[data-testid*="stop"]',
                )
                if any(b.is_displayed() for b in stop_btns):
                    continue
            except Exception:
                pass

            els = driver.find_elements(
                By.CSS_SELECTOR,
                '[data-message-author-role="assistant"]',
            )
            if not els:
                continue
            text = (els[-1].text or "").strip()
            if len(text) < 3:
                continue
            if text == last_assistant:
                stable_rounds += 1
                if stable_rounds >= 2:
                    answer = text
                    driver.close()
                    driver.switch_to.window(form_handle)
                    time.sleep(0.4)
                    log.info("ChatGPT reply captured (%d chars)", len(answer))
                    return answer
            else:
                stable_rounds = 0
                last_assistant = text

        answer = last_assistant
        driver.close()
        driver.switch_to.window(form_handle)
        time.sleep(0.4)
        if answer:
            log.info("ChatGPT: using partial/stale reply (%d chars)", len(answer))
        return answer.strip()

    except Exception as e:
        log.exception("ChatGPT browser step failed: %s", e)
        try:
            for h in driver.window_handles:
                if h != form_handle:
                    driver.switch_to.window(h)
                    driver.close()
                    break
            driver.switch_to.window(form_handle)
        except Exception:
            pass
        return ""

# -------------------------------
# Submit / browser helpers
# -------------------------------
def click_submit(driver: webdriver.Chrome) -> None:
    try:
        for el in driver.find_elements(By.XPATH, "//button | //*[@role='button']"):
            t = (el.text or "").strip()
            if t and re.search(r"submit|إرسال", t, re.I):
                el.click()
                log.info("Clicked submit")
                return
        for el in driver.find_elements(By.CSS_SELECTOR, 'div[role="button"], span, button'):
            t = (el.text or "").strip()
            if t and "submit" in t.lower():
                el.click()
                log.info("Clicked submit (fallback)")
                return
    except Exception:
        pass
    log.warning("Submit button not found")

def build_chrome_options(
    *,
    headless: bool,
    user_data_dir: Path | None,
    extra_args: list[str] | None,
) -> Options:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    if user_data_dir is not None:
        p = str(user_data_dir.resolve())
        if not user_data_dir.is_dir():
            user_data_dir.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={p}")
    for a in extra_args or []:
        a = (a or "").strip()
        if a:
            options.add_argument(a)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return options

def create_chrome_driver(options: Options) -> webdriver.Chrome:
    return webdriver.Chrome(options=options)

# -------------------------------
# Main runner
# -------------------------------
def run_form_bot(
    *,
    form_url: str,
    resume_path: Path,
    text_answers: dict[str, str],
    radio_answers: dict[str, str],
    use_placeholder_for_unknown: bool,
    unknown_placeholder: str,
    headed: bool,
    slow_mo_ms: int,
    wait_for_login: bool,
    use_chatgpt_browser: bool = True,
    chatgpt_url: str = "https://chatgpt.com",
    chatgpt_response_timeout_sec: float = 120.0,
    chatgpt_prompt_wait_sec: float = 45.0,
    chatgpt_max_resume_chars: int = 12000,
    browser_profile_dir: Path | None = None,
    browser_launch_args: list[str] | None = None,
    add_file_button_image: Path | None = None,
    insert_file_image: Path | None = None,
    browse_button_image: Path | None = None,
    image_confidence: float = 0.85,
    image_wait_timeout: float = 60.0,
    upload_poll_sec: float = 0.5,
    upload_loading_timeout_sec: float = 120.0,
    upload_max_browse_retries: int = 5,
) -> None:
    resume_text = load_resume_text(resume_path)
    log.info("Resume excerpt length: %d chars", len(resume_text))

    options = build_chrome_options(
        headless=not headed,
        user_data_dir=browser_profile_dir,
        extra_args=browser_launch_args,
    )
    log.info("Starting Chrome via Selenium (profile dir: %s)", browser_profile_dir or "default temp profile")

    driver = create_chrome_driver(options)
    try:
        if headed:
            try:
                driver.maximize_window()
            except Exception as e:
                log.debug("Could not maximize Chrome window: %s", e)
        driver.set_page_load_timeout(120)
        driver.implicitly_wait(1)
        log.info("Opening form (browser visible: %s)", headed)
        driver.get(form_url)
        time.sleep(2 + min(slow_mo_ms / 1000.0, 2.0))

        if wait_for_login:
            log.info("Waiting for you to sign in / dismiss dialogs if needed...")
            input("Press Enter here when the form questions are visible... ")

        handled_file_global = False
        seen_q: set[str] = set()

        for section in iter_sections(driver):
            q = section_question_text(section)
            if not q or len(q) < 2:
                continue
            dedupe = q.strip().lower()[:240]
            if dedupe in seen_q:
                continue
            seen_q.add(dedupe)
            log.info("--- Question: %s", q[:120] + ("…" if len(q) > 120 else ""))
            time.sleep(slow_mo_ms / 1000.0 if slow_mo_ms else 0)

            if section_has_add_file(section) and upload_resume_google_form(
                driver,
                resume_path,
                section,
                headed=headed,
                add_file_button_image=add_file_button_image,
                insert_file_image=insert_file_image,
                browse_button_image=browse_button_image,
                image_confidence=image_confidence,
                image_wait_timeout=image_wait_timeout,
                upload_poll_sec=upload_poll_sec,
                upload_loading_timeout_sec=upload_loading_timeout_sec,
                upload_max_browse_retries=upload_max_browse_retries,
            ):
                handled_file_global = True
                continue

            text_key = match_mapping(q, text_answers)
            if text_key is not None:
                ok = fill_text_in_section(section, text_key)
                log.info("Filled text field: %s", "ok" if ok else "FAILED")
                continue

            # Radio
            radio_key = match_mapping(q, radio_answers)
            if radio_key is not None:
                ok = click_radio_by_label(section, radio_key)
                log.info("Selected radio: %s", "ok" if ok else "FAILED")
                continue

            # Unknown
            if use_placeholder_for_unknown or not use_chatgpt_browser:
                log.info("(Unknown) Using placeholder (ChatGPT disabled or placeholder mode)")
                filled = fill_text_in_section(section, unknown_placeholder)
                if not filled:
                    log.warning("Could not fill unknown section (no text control found)")
                continue

            log.info("(ChatGPT) Unknown question — new tab, question + resume (no API key)")
            answer = ask_chatgpt_via_browser(
                driver,
                q,
                resume_text,
                headed=headed,
                chatgpt_url=chatgpt_url,
                response_timeout_sec=chatgpt_response_timeout_sec,
                prompt_wait_sec=chatgpt_prompt_wait_sec,
                max_resume_chars=chatgpt_max_resume_chars,
            )
            if not answer:
                answer = unknown_placeholder
            log.info("(ChatGPT) Answer length: %d chars", len(answer))
            ok = fill_text_in_section(section, answer)
            if not ok:
                first_line = (answer.splitlines()[0] if answer else "").strip()
                if first_line:
                    ok = click_radio_by_label(section, first_line)
            if not ok and answer:
                ok = click_radio_by_label(section, answer.strip()[:80])
            log.info("Filled ChatGPT answer: %s", "ok" if ok else "FAILED")

        # Fallback global file input
        if not handled_file_global:
            inps = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            if inps:
                inps[0].send_keys(str(resume_path.resolve()))
                log.info("Uploaded resume (global file input)")

        time.sleep(0.5 + (slow_mo_ms / 1000.0 if slow_mo_ms else 0))
        click_submit(driver)
        time.sleep(3)
    finally:
        driver.quit()