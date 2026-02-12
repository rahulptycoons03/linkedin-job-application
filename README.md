# LinkedIn Easy Apply Bot

Automatically apply to **LinkedIn Easy Apply** jobs using a simple configuration file. No coding required!

The bot opens Chrome, logs into your LinkedIn account, searches for jobs matching your keywords and location, and applies to each one automatically.

---

## Features

- Applies to LinkedIn "Easy Apply" jobs automatically
- Supports **multiple profiles** running at the same time (different accounts, different job searches)
- Automatically fills in common application fields:
  - Years of experience
  - Phone number
  - City / location
  - Salary expectation
  - Sponsorship questions ("No" by default)
  - Work authorization questions ("Yes" by default)
  - Cover letter / free-text answers
- Handles multi-step application forms (clicks Next, Review, Submit)
- Detects when an application gets stuck and skips it
- Saves screenshots for debugging
- Logs every action with timestamps

---

## Requirements

Before you start, make sure you have:

1. **Windows 10 or 11**
2. **Google Chrome** browser installed ([Download Chrome](https://www.google.com/chrome/))
3. **Python 3.9 or newer** ([Download Python](https://www.python.org/downloads/))
   - **IMPORTANT**: During Python installation, check the box that says **"Add Python to PATH"**

---

## Quick Start (Step by Step)

### Step 1: Download this project

Click the green **"Code"** button on GitHub, then click **"Download ZIP"**.
Extract the ZIP file to a folder on your computer (e.g., `C:\linkedin-bot`).

### Step 2: Install dependencies

1. Open the folder where you extracted the files
2. **Double-click `install.bat`**
3. Wait for it to finish (it will say "Setup complete!")

### Step 3: Create your profile

1. Go to the `profiles` folder
2. Copy one of the example files:
   - `example_data_engineer.json` - for Data Engineer jobs
   - `example_helpdesk_admin.json` - for Helpdesk / Admin jobs
   - `example_singapore.json` - for jobs in Singapore
3. Rename your copy to something like `my_profile.json`
4. Open it with **Notepad** and fill in your details:

```json
{
    "linkedin_email": "your_real_email@gmail.com",
    "linkedin_password": "your_real_password",

    "keywords": ["data engineer", "etl engineer"],
    "location": "Melbourne, Victoria, Australia",
    "max_applications": 50,

    "phone_number": "0412345678",
    "years_of_experience": "5"
}
```

5. Save the file

### Step 4: Run the bot

1. **Double-click `run.bat`**
2. It will ask you to enter your profile filename (e.g., `my_profile.json`)
3. Chrome will open and start applying!

**If LinkedIn asks for a CAPTCHA or verification**, complete it manually in the browser window. The bot will wait 60 seconds for you.

---

## Running Multiple Profiles at Once

Want to run multiple job searches at the same time? (e.g., different accounts or different job types)

1. Create a separate `.json` file in the `profiles` folder for each search
2. **Double-click `run_all.bat`**
3. Each profile will open in its own Chrome window

---

## Profile Configuration Reference

Here's what each field in the profile JSON file does:

| Field | Required? | Description | Example |
|-------|-----------|-------------|---------|
| `linkedin_email` | Yes | Your LinkedIn login email | `"user@gmail.com"` |
| `linkedin_password` | Yes | Your LinkedIn password | `"MyP@ssword"` |
| `keywords` | Yes | Job titles to search for (list) | `["data engineer", "etl engineer"]` |
| `location` | Yes | City/region to search in | `"Melbourne, Victoria, Australia"` |
| `max_applications` | No | Max jobs to apply to (default: 50) | `50` |
| `search_radius_km` | No | Search radius in km (default: 100) | `100` |
| `phone_number` | No | Your phone number for applications | `"0412345678"` |
| `linkedin_profile_url` | No | Your LinkedIn profile URL | `"https://linkedin.com/in/you"` |
| `years_of_experience` | No | Years of experience (default: "5") | `"5"` |
| `salary_expectation` | No | Expected salary | `"120000"` |
| `notice_period` | No | Your notice period (default: "2 weeks") | `"2 weeks"` |
| `city_for_forms` | No | City name for form fields | `"Melbourne"` |
| `requires_sponsorship` | No | Do you need visa sponsorship? (default: false) | `false` |
| `work_authorized` | No | Are you authorized to work? (default: true) | `true` |
| `cover_letter_text` | No | Text for cover letter / "why interested" fields | `"I have 5 years..."` |
| `default_answer_text` | No | Default text for other free-text fields | `"Experienced..."` |
| `sponsorship_answer_text` | No | Custom answer for sponsorship questions | `"No, I don't need..."` |
| `work_auth_answer_text` | No | Custom answer for work auth questions | `"Yes, I am..."` |

---

## Standalone Scripts (Advanced)

If you prefer using the standalone scripts (without JSON config), these are included:

| Script | Account | Location | Job Type |
|--------|---------|----------|----------|
| `linkedin_easy_apply_rahul_au.py` | Rahul (main) | Melbourne, AU | Data Engineer |
| `linkedin_easy_apply_manu_au.py` | Manu | Melbourne, AU | Helpdesk / Admin |
| `linkedin_easy_apply_rahul_sg.py` | Rahul (2nd) | Singapore | Data Engineer |

Run them directly:
```
python linkedin_easy_apply_rahul_au.py
```

---

## Troubleshooting

### "Python is not installed"
Download Python from https://www.python.org/downloads/ and make sure to check **"Add Python to PATH"** during installation.

### "ChromeDriver version mismatch"
Update Chrome to the latest version, or run `pip install --upgrade selenium` in the virtual environment.

### Bot gets stuck on login
If LinkedIn shows a CAPTCHA or verification, complete it manually in the browser. The bot waits 60 seconds for you.

### Bot keeps skipping jobs
This usually means required fields aren't being filled correctly. Check the `logs/screenshots` folder for screenshots that show what went wrong.

### "No Easy Apply jobs found"
Try broader keywords or a different location. Not all jobs have "Easy Apply" enabled.

---

## File Structure

```
linkedin-easy-apply/
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── install.bat                        # One-click setup (Windows)
├── run.bat                            # Run with a single profile
├── run_all.bat                        # Run all profiles in parallel
├── .gitignore                         # Files to exclude from git
│
├── linkedin_easy_apply_bot.py         # Main bot (config-based)
├── linkedin_easy_apply_rahul_au.py    # Standalone: Rahul AU
├── linkedin_easy_apply_manu_au.py     # Standalone: Manu AU
├── linkedin_easy_apply_rahul_sg.py    # Standalone: Rahul SG
│
├── profiles/                          # Profile configurations
│   ├── example_data_engineer.json     # Example: Data Engineer
│   ├── example_helpdesk_admin.json    # Example: Helpdesk/Admin
│   └── example_singapore.json         # Example: Singapore
│
├── robot/                             # Robot Framework files (optional)
│   ├── LinkedInEasyApplyLibrary.py
│   ├── LinkedInKeywords.robot
│   ├── linkedin_easy_apply_au.robot
│   ├── linkedin_easy_apply_sg.robot
│   ├── vars_linkedin_au.py
│   └── vars_linkedin_sg.py
│
└── logs/                              # Logs & screenshots (auto-created)
    └── screenshots/
```

---

## Disclaimer

This tool is for educational purposes. Use it responsibly and in accordance with LinkedIn's Terms of Service. The authors are not responsible for any consequences of using this tool.

---

## License

MIT License - Copyright (c) 2026 Rahul Poolanchalil. Free to use, modify, and share.
