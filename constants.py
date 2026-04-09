# Edit for your machine. Do not commit secrets.
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

FORM_URL = (
    "https://docs.google.com/forms/d/e/1FAIpQLSfinizt6aXjemupnF2SHWoCd3GjQMOVCCvUOHkrHFAjIg3Lfw/viewform"
)

RESUME_PATH = r"D:\my python\web form bot\resume\mohamed_elsayed.pdf"

TEXT_ANSWERS = {
    "first name": "Mohamed",
    "last name": "Elsmin",
    "email": "mohamedelsamin12@gmail.com",
    "number": "01208557874",
    "Which field are you interested in ?": "AI and Machine Learning",
}

RADIO_ANSWERS = {
    "Gender": "Male",
}

# True = never open ChatGPT for unknowns; use UNKNOWN_PLACEHOLDER only
USE_PLACEHOLDER_FOR_UNKNOWN = False
UNKNOWN_PLACEHOLDER = "See resume — details provided in uploaded CV."

CHATGPT_URL = "https://chatgpt.com"
CHATGPT_RESPONSE_TIMEOUT_SEC = 120
CHATGPT_PROMPT_WAIT_SEC = 45
CHATGPT_MAX_RESUME_CHARS = 12000

# Selenium: Chrome user-data dir + profile (close Chrome before running)
BROWSER_PROFILE_DIR = r"C:\Users\Mohamed\ChromeAutomationProfile"
BROWSER_LAUNCH_ARGS = []

ADD_FILE_BUTTON_IMAGE = _ROOT / "assets" / "add_file.png"
INSERT_FILE_IMAGE = _ROOT / "assets" / "insert_file.png"
BROWSE_BUTTON_IMAGE = _ROOT / "assets" / "browse_button.png"
IMAGE_MATCH_CONFIDENCE = 0.85
IMAGE_WAIT_TIMEOUT_SEC = 60

# After path+Enter: re-check insert/browse templates (poll / loading / retry Browse)
UPLOAD_IMAGE_POLL_SEC = 0.5
UPLOAD_LOADING_TIMEOUT_SEC = 120
UPLOAD_MAX_BROWSE_RETRIES = 5
