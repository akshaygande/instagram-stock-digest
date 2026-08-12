# Daily Instagram Stock Digest

Automated pipeline that scrapes your Instagram stock research pages, transcribes Reels, summarizes everything with AI (Gemini 1.5 Flash), and delivers a structured digest to your **Telegram at 8:00 AM IST** every day — **100% free**.

---

## How It Works

```
GitHub Actions (free cron)
    ↓ 8:00 AM IST daily
Instaloader  →  scrapes posts & reels (last 24h)
    ↓
Whisper tiny →  transcribes reel audio → text
    ↓
Gemini 1.5 Flash → AI digest (stocks, news, levels)
    ↓
Telegram Bot →  sends to your chat
```

---

## One-Time Setup (15 minutes total)

### Step 1 — Create a private GitHub repo

1. Go to [github.com/new](https://github.com/new)
2. Name it `instagram-stock-digest`
3. Set it to **Private**
4. Click **Create repository** (don't initialize with README)

### Step 2 — Push this code to your repo

Open Terminal and run:

```bash
cd "/Users/gandeakshay/Documents/instagram-stock-digest"
git init
git add .
git commit -m "Initial setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/instagram-stock-digest.git
git push -u origin main
```

> Replace `YOUR_USERNAME` with your actual GitHub username.

---

### Step 3 — Create your Telegram Bot (2 minutes)

1. Open Telegram and search for **@BotFather**
2. Send: `/newbot`
3. Give it a name: e.g. `Stock Digest`
4. Give it a username: e.g. `mystockdigest_bot`
5. BotFather will send you a **token** like:
   ```
   7412345678:AAHx_abcdefghijklmnopqrstuvwxyz12345
   ```
   **Save this — it's your `TELEGRAM_BOT_TOKEN`.**

6. **Start a chat with your new bot** by clicking the link BotFather gives you and pressing `/start`

7. **Get your Chat ID** — open this URL in your browser (replace `YOUR_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
   Look for `"id"` inside `"chat"`. That number is your `TELEGRAM_CHAT_ID`.

---

### Step 4 — Get your Gemini API key (30 seconds)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Copy the key — this is your `GEMINI_API_KEY`

> Free tier: 1,500 requests/day — more than enough.

---

### Step 5 — Set up GitHub Secrets

In your GitHub repo:
1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** for each of the following:

| Secret Name | Value |
|---|---|
| `INSTAGRAM_USERNAME` | Your Instagram username (ideally a dummy/alt account) |
| `INSTAGRAM_PASSWORD` | Your Instagram password |
| `GEMINI_API_KEY` | From Step 4 |
| `TELEGRAM_BOT_TOKEN` | From Step 3 |
| `TELEGRAM_CHAT_ID` | From Step 3 |

> **Tip**: Using a dummy Instagram account (not your main) reduces risk of your primary account being flagged.

---

### Step 6 — Add your pages

Edit [`config/pages.txt`](config/pages.txt) and add the Instagram usernames you want to track (one per line, no `@`):

```
zerodha
stockmarketindia
nse_india
your_favourite_analyst
```

Commit and push:
```bash
git add config/pages.txt
git commit -m "Add tracked pages"
git push
```

---

### Step 7 — Test it manually

1. Go to your repo on GitHub
2. Click **Actions** tab
3. Click **Daily Stock Digest** on the left
4. Click **Run workflow** → **Run workflow**
5. Watch the logs — in ~5 minutes you should get a Telegram message! 🎉

---

## Daily Schedule

The workflow runs automatically at **2:30 AM UTC = 8:00 AM IST**.

To change the time, edit `.github/workflows/daily_digest.yml`:
```yaml
- cron: '30 2 * * *'   # 2:30 AM UTC = 8:00 AM IST
```

Use [crontab.guru](https://crontab.guru) to convert your preferred time to UTC.

---

## What the Digest Looks Like

```
📊 STOCK DIGEST — 12 Aug 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 23 new post(s) from 16 page(s)

📈 STOCKS & INDICES MENTIONED
• RELIANCE — Breakout above ₹2980 flagged (@marketwalah)
• HDFC BANK — Q1 NIM expansion, strong buying (@zerodha)
• NIFTY — Resistance at 25,200 highlighted (@nse_india)

📰 KEY NEWS & EVENTS
• RBI policy: Rate hold expected in October
• FII inflows ₹2,400 Cr in last session

💡 ANALYST VIEWS
• Mid-cap correction = buying opportunity (@varsity)
• IT sector rotation expected in Q3 (@stockresearch_in)

⚠️ RISKS & WARNINGS
• Global crude spike could pressure OMCs
• Weak monsoon data affecting agri sector

🎯 ACTIONABLE LEVELS
• NIFTY: Watch 25,200 for breakout confirmation
• HDFC BANK: Dip to ₹1,680 is a buy zone

Sentiment: BULLISH — FII inflows and earnings beats dominate
```

---

## Cost Breakdown

| Component | Free Tier | Your Usage |
|---|---|---|
| GitHub Actions | 2,000 min/month | ~30 min/day = 900 min/month ✅ |
| Gemini 1.5 Flash | 1,500 req/day | 1 req/day ✅ |
| Telegram Bot API | Unlimited | 1-3 messages/day ✅ |
| **Total** | | **$0/month** ✅ |

---

## Troubleshooting

**No message received?**
- Check GitHub Actions logs (Actions tab → last run → click the job)
- Verify all 5 secrets are set correctly

**Instagram login failing?**
- Instagram may have flagged the IP. Wait 24h, it usually resolves.
- Make sure your Instagram account doesn't have 2FA enabled.
- Try logging into the account manually first to clear any security prompts.

**"Profile not found" errors?**
- Double-check the username spelling in `config/pages.txt` (no `@`, lowercase)

**Telegram Chat ID is wrong?**
- Go to `https://api.telegram.org/botYOUR_TOKEN/getUpdates` and look for the `id` field inside the `chat` object

---

## File Structure

```
instagram-stock-digest/
├── .github/workflows/
│   └── daily_digest.yml    ← Cron job (runs at 8 AM IST)
├── config/
│   └── pages.txt           ← Your Instagram pages list
├── src/
│   ├── scraper.py          ← Instaloader-based scraper
│   ├── transcriber.py      ← Whisper audio transcription
│   ├── summarizer.py       ← Gemini AI summarization
│   └── notifier.py         ← Telegram Bot delivery
├── state/
│   └── processed_posts.json ← Tracks already-sent posts (auto-updated)
├── main.py                 ← Orchestrator
└── requirements.txt
```
