# Daily Briefing Agent

A simple Python script that fetches today’s top headlines from NewsAPI, summarizes them in *N* bullet points and fact-checks each bullet using Google’s Gemini API, then emails you the result.

---

## Features

- **Real headlines** via [NewsAPI.org](https://newsapi.org/)  
- **Summarization & Fact-Checking** with Google Gemini (`ChatGoogleGenerativeAI`)  
- **Simple CLI** or background scheduling via `schedule`  
- **Email Delivery** through any SMTP server (e.g., Gmail with App Password)  
- **Easy to Fork & Run** on any machine or in GitHub Actions

---

## Quick Start

### 1. Fork & Clone

```bash
git clone https://github.com/your-username/daily-briefing-agent.git
cd daily-briefing-agent
```

### 2. Create & Activate Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate     # Windows PowerShell
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt 
```

*(If you only run in GitHub Actions, you can omit `schedule`.)*

### 4. Provision API Keys & Email Credentials

Create a file named `.env` in the project root:
Refer .env.example (for local use)

```ini
# .env
GOOGLE_API_KEY=your_gemini_api_key_here
NEWS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_ADDRESS=you@example.com
EMAIL_PASSWORD=your_email_app_password
```

> **Note:**  
> - For Gmail with 2FA, generate an **App Password** under Google Account → Security → App passwords.  

### 5. Run the Script

```bash
python daily_briefing.py
```

You should see a summary printed and receive it via email.

---

## Scheduling

### A) Local Scheduling with `schedule`

Uncomment the scheduler lines at the bottom of `daily_briefing.py`:

```python
if __name__ == "__main__":
    run_briefing()
    # schedule.every().day.at("08:00").do(run_briefing)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(30)
```

1. Keep the script running (e.g., in `tmux` or `nohup`).

> **Time Format:** `at("08:00")` uses your machine’s local 24‑hour clock.

### B) GitHub Actions

1. **Add Secrets** in _Settings → Secrets → Actions_:  
   `GOOGLE_API_KEY`, `NEWS_API_KEY`, `EMAIL_SMTP_SERVER`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`.

2. **Create** `.github/workflows/daily_briefing.yml`:

3. **Push** to GitHub—your action will send the briefing at the scheduled time.

---

## Configuration

- **Change Number of Headlines:** adjust `page_size` in `get_top_headlines(...)`.  
- **Change Bullet Count:** update the argument `n` passed to `make_prompt(raw, n)`.  
- **Modify Regions:** adjust parameters in `get_top_headlines(country="us", ...)`.

---