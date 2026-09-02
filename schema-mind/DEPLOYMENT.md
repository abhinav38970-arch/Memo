# 🚀 DEPLOYMENT GUIDE — SchemaMind

## What You're Deploying

| Part | Platform | What it is |
|------|----------|------------|
| **Backend** | Render (Web Service) | FastAPI + Groq API |
| **Frontend** | Vercel | Next.js 14 app |

**The Groq API key is already embedded in:**
- `backend/.env.example`
- `backend/app/services/groq_client.py` (hardcoded fallback)
- `backend/render.yaml` (for Render deployment)

So you don't need to set it up manually.

---

## STEP 1: Push to GitHub

```bash
# Create a new repo on GitHub first (don't initialize with README)
# Then:
cd schema-mind
git init
git add .
git commit -m "SchemaMind MVP"
git remote add origin https://github.com/YOUR_USERNAME/schema-mind.git
git push -u origin main
```

> **Important:** Don't worry about the API key being in the repo — it's a hackathon MVP. For a real product you'd use environment variables.

---

## STEP 2: Deploy Backend to Render

### 2a. Create a Render Account
1. Go to https://dashboard.render.com
2. Sign up with GitHub (easiest)

### 2b. Create New Web Service
1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repo
3. Fill in the form:

| Field | Value |
|-------|-------|
| **Name** | `schema-mind-api` |
| **Region** | Choose closest to you (e.g. Oregon) |
| **Branch** | `main` |
| **Root Directory** | `schema-mind/backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | **Free** (starts at $0) |

4. Click **"Advanced"** and add:
   - **Health Check Path**: `/api/health`
   - Environment variables (all optional — sensible defaults are built in):

     | Key | Value | Why |
     |-----|-------|-----|
     | `GROQ_API_KEY` | your key | falls back to the embedded hackathon key |
     | `GROQ_MODEL` | `openai/gpt-oss-120b` | current recommended Groq model |
     | `GROQ_TPM_LIMIT` | `8000` | Groq **free tier** tokens/min. If you upgrade to the Developer plan, set your new limit here |
     | `PYTHON_VERSION` | `3.11.9` | also pinned via `.python-version` |

5. Click **"Create Web Service"**

### 2c. Wait for Deploy
- Render will build and deploy (~2 minutes)
- Once done, you'll get a URL like: `https://schema-mind-api.onrender.com`

### 2d. Verify Backend
Open `https://schema-mind-api.onrender.com/api/health` in your browser.
You should see:
```json
{"status": "ok", "model": "openai/gpt-oss-120b", "groq": {"tpm_limit": 8000, "...": "..."}}
```

The `groq` block shows the effective configuration (model, tokens-per-minute limit, reasoning
effort) so you can confirm your environment variables were picked up.

---

## STEP 3: Deploy Frontend to Vercel

### 3a. Create a Vercel Account
1. Go to https://vercel.com
2. Sign up with GitHub

### 3b. Import Your Repo
1. Click **"Add New..."** → **"Project"**
2. Find and select your `schema-mind` repo
3. **Important:** Set the **Root Directory** to `frontend`

### 3c. Configure Environment Variables
In the Vercel project settings (or during import), add:

| Key | Value |
|-----|-------|
| `NEXT_PUBLIC_API_URL` | `https://schema-mind-api.onrender.com` |

(Replace with your actual Render URL from Step 2c)

### 3d. Deploy
1. Click **"Deploy"**
2. Wait ~1-2 minutes
3. You'll get a URL like: `https://schema-mind.vercel.app`

### 3e. (Optional) Custom Domain
Go to Project → Settings → Domains and add your own domain.

---

## STEP 4: Verify Everything Works

1. Open your Vercel URL (e.g. `https://schema-mind.vercel.app`)
2. ✅ Landing page loads with video background
3. ✅ Click **"Get Started"** or **"Try SchemaMind"**
4. ✅ Onboarding page loads at `/pp`
5. ✅ Pick a pattern type or describe your own
6. ✅ Click "Continue" → paste some text → "Generate Patterns"
7. ✅ Patterns appear
8. ✅ Quiz works
9. ✅ Results screen shows

---

## Troubleshooting

### "Failed to generate patterns" error
- Check that your Render backend is running:
  - Open `https://your-app.onrender.com/api/health`
  - If it doesn't load, check Render logs
- Check that `NEXT_PUBLIC_API_URL` is set correctly in Vercel:
  - Go to Vercel → Project → Settings → Environment Variables
  - Make sure the value ends WITHOUT a trailing slash

### Groq `413 Request too large ... tokens per minute (TPM): Limit 8000, Requested 8665`
Groq's free tier allows 8,000 tokens per minute for `openai/gpt-oss-120b` and charges
`prompt + max_tokens` up front. The backend now sizes every request to fit that budget
automatically, so this should not happen anymore. If you still see it:
- Make sure Render deployed the latest `main` (Render dashboard → Manual Deploy → Deploy latest commit).
- Check `GROQ_TPM_LIMIT` isn't set higher than your real limit (see https://console.groq.com/settings/limits).

### "The AI is rate-limited right now" (HTTP 429)
The per-minute budget for the whole Groq organization is used up (every generate/quiz/adapt
call spends a few thousand tokens). Wait for the countdown in the UI and retry, or upgrade
the Groq plan and raise `GROQ_TPM_LIMIT`.

### The first request takes ~1 minute
Render's free tier puts the backend to sleep after 15 minutes of inactivity; the first request
wakes it up. The UI shows a hint after a few seconds — just wait, it will complete.

### Backend deploy fails
- Go to Render dashboard → your service → **"Logs"**
- The most common issue: Python version. Make sure it's set to Python 3.x.
- If you see `uvicorn: command not found`, check the Build Command

### CORS errors in browser
The backend already allows all origins (`allow_origins=["*"]`) so CORS should work.

### Want to test locally first?
```bash
# Terminal 1: Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

Then open `http://localhost:3000`

---

## Good luck at the hackathon! 🚀