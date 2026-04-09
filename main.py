"""
Entry point: run `python main.py` to fill Google Form automatically.
"""
from pathlib import Path
import sys
import logging
import os
import webbrowser

from dotenv import load_dotenv

from form_bot import run_form_bot


def main_sync():
    import argparse

    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )
    log = logging.getLogger("main")

    parser = argparse.ArgumentParser(description="Fill a Google Form from constants (Selenium).")
    parser.add_argument("--headless", action="store_true", help="Hide browser")
    parser.add_argument("--slowmo", type=int, default=350, help="Slow motion ms (0 = off)")
    parser.add_argument(
        "--no-chatgpt",
        action="store_true",
        help="Do not open ChatGPT for unknowns; use UNKNOWN_PLACEHOLDER only",
    )
    parser.add_argument("--wait-login", action="store_true", help="Pause for Enter after load for Google login")
    parser.add_argument("--open-only", action="store_true", help="Open FORM_URL in default browser then exit")
    args = parser.parse_args()

    try:
        import constants as C
    except ImportError:
        print("Copy constants.example.py to constants.py and edit it.")
        sys.exit(1)

    resume = Path(C.RESUME_PATH)
    use_chatgpt = not args.no_chatgpt and not getattr(C, "USE_PLACEHOLDER_FOR_UNKNOWN", False)
    if use_chatgpt and args.headless:
        log.warning("Headless + ChatGPT web: unknown answers will fail; use headed Chrome or --no-chatgpt")

    chatgpt_url = (os.environ.get("CHATGPT_URL") or getattr(C, "CHATGPT_URL", "https://chatgpt.com")).strip()

    profile_path = Path(getattr(C, "BROWSER_PROFILE_DIR", "")) if getattr(C, "BROWSER_PROFILE_DIR", None) else None
    launch_args = getattr(C, "BROWSER_LAUNCH_ARGS", None)
    if not isinstance(launch_args, list):
        launch_args = None

    if args.open_only:
        webbrowser.open(C.FORM_URL, new=1)
        log.info("Opened default browser with form URL")
        return

    def _pimg(name: str):
        v = getattr(C, name, None)
        return Path(v) if v is not None else None

    run_form_bot(
        form_url=C.FORM_URL,
        resume_path=resume,
        text_answers=C.TEXT_ANSWERS,
        radio_answers=C.RADIO_ANSWERS,
        use_placeholder_for_unknown=not use_chatgpt,
        unknown_placeholder=getattr(C, "UNKNOWN_PLACEHOLDER", "See resume."),
        headed=not args.headless,
        slow_mo_ms=args.slowmo,
        wait_for_login=args.wait_login,
        use_chatgpt_browser=use_chatgpt,
        chatgpt_url=chatgpt_url,
        chatgpt_response_timeout_sec=float(getattr(C, "CHATGPT_RESPONSE_TIMEOUT_SEC", 120.0)),
        chatgpt_prompt_wait_sec=float(getattr(C, "CHATGPT_PROMPT_WAIT_SEC", 45.0)),
        chatgpt_max_resume_chars=int(getattr(C, "CHATGPT_MAX_RESUME_CHARS", 12000)),
        browser_profile_dir=profile_path,
        browser_launch_args=launch_args,
        add_file_button_image=_pimg("ADD_FILE_BUTTON_IMAGE"),
        insert_file_image=_pimg("INSERT_FILE_IMAGE"),
        browse_button_image=_pimg("BROWSE_BUTTON_IMAGE"),
        image_confidence=float(getattr(C, "IMAGE_MATCH_CONFIDENCE", 0.85)),
        image_wait_timeout=float(getattr(C, "IMAGE_WAIT_TIMEOUT_SEC", 60.0)),
        upload_poll_sec=float(getattr(C, "UPLOAD_IMAGE_POLL_SEC", 0.5)),
        upload_loading_timeout_sec=float(getattr(C, "UPLOAD_LOADING_TIMEOUT_SEC", 120.0)),
        upload_max_browse_retries=int(getattr(C, "UPLOAD_MAX_BROWSE_RETRIES", 5)),
    )


if __name__ == "__main__":
    main_sync()
