# AIAssistedFormBot
AIAssistedFormBot is a hybrid Google Forms automation bot built with Python.
It combines browser automation, computer vision, and AI-assisted workflows to intelligently complete forms end-to-end.

This project demonstrates a practical Intelligent RPA approach capable of handling dynamic UI behavior and native system dialogs.

## 🚀 Key Features
### 🔹 Real Chrome Profile Integration
- Uses your existing Chrome user profile
- No login automation required
- Reuses authenticated sessions (Google + ChatGPT)

### 🔹 Structured Form Automation
- Predefined answers stored in ``` constants.py ```
- Supports:
  - Text inputs
  - Radio buttons
  - Smart substring-based question matching

### 🔹 Intelligent File Upload Handling

- Google Forms file uploads trigger a native Windows dialog that Selenium cannot control directly.

- To solve this, the bot uses:

  - OpenCV (template matching)
  - PyAutoGUI (UI automation)
  - Clipboard-based path injection

- Flow:
```
Add file → Detect upload UI → Click Browse → Paste resume path → Confirm
```
- Includes:

  - Image polling
  - Upload state detection
  - Retry mechanism
  - Iframe fallback support

### 🔹 AI-Assisted Dynamic Question Handling (No API Key)

- For unknown or unmapped questions:

  - Opens ChatGPT in a new browser tab
  - Sends the question + résumé content
  - Waits for the assistant reply
  - Extracts the final response
  - Injects it back into the form

All inside the existing authenticated Chrome session.

## Automation Flow
```
Load Form  
   │  
   ├── Known Question → Fill via constants  
   │  
   ├── File Upload → Computer Vision Layer  
   │  
   └── Unknown Question  
           │  
           ├── Open ChatGPT tab  
           └── Inject generated answer  
  ```

## Configuration

Edit ```constants.py```:
```
FORM_URL = "your_google_form_url"
RESUME_PATH = r"path_to_resume.pdf"

TEXT_ANSWERS = {
    "first name": "Your Name",
    "email": "your@email.com",
}

RADIO_ANSWERS = {
    "Gender": "Male",
}
```
