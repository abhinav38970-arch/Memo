# SchemaMind

**SchemaMind** is an AI-powered learning tool that transforms any text into personalized memory patterns. Paste your material, tell the AI how YOUR brain remembers things, and it generates customized study aids — acronyms, analogies, stories, or any custom method you describe. Then quiz yourself until it sticks.

---

## Architecture

```
schema-mind/
├── backend/               # FastAPI + Groq (deploy on Render)
│   ├── app/
│   │   ├── main.py        # FastAPI entry point + CORS
│   │   ├── models/        # Pydantic schemas
│   │   ├── routers/       # API endpoints
│   │   │   ├── health.py
│   │   │   ├── patterns.py
│   │   │   ├── quiz.py
│   │   │   └── adaptation.py
│   │   └── services/      # Business logic + Groq client
│   │       ├── groq_client.py
│   │       ├── pattern_service.py
│   │       ├── quiz_service.py
│   │       └── adaptation_service.py
│   ├── requirements.txt
│   └── render.yaml
│
├── frontend/              # Next.js 14 + Tailwind (deploy on Vercel)
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx      # Video background + root layout
│   │   │   ├── page.tsx        # Landing page (scrollable)
│   │   │   ├── pp/page.tsx     # Memorization tool page
│   │   │   └── globals.css     # All styles + animations
│   │   └── components/
│   ├── public/
│   │   ├── assets/             # logo.webp (replace with your own)
│   │   └── fonts/              # GeistPixel-Circle.woff2 (add your own)
│   ├── package.json
│   ├── next.config.mjs
│   └── tailwind.config.ts
│
└── schema-mind-spec.md    # Full project specification
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/generate-patterns` | Generate memory patterns from text + preferences |
| POST | `/api/generate-quiz` | Generate quiz questions from patterns |
| POST | `/api/check-answer` | Check a user's answer (simple match) |
| POST | `/api/adapt-patterns` | Regenerate patterns based on wrong answers |

---

## Setup & Deployment

### Backend (Render)

1. Create a Render Web Service connected to your repo or upload the `/backend` folder
2. Set the **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add environment variable: `GROQ_API_KEY` (get yours at https://console.groq.com)
4. Optional: `GROQ_MODEL` (default: `mixtral-8x7b-32768`)

### Frontend (Vercel)

1. Connect your repo to Vercel
2. Set **Root Directory**: `frontend`
3. Add environment variable: `NEXT_PUBLIC_API_URL` = your Render URL
4. Deploy!

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your GROQ_API_KEY
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
cp .env.local.example .env.local  # Add NEXT_PUBLIC_API_URL
npm run dev
```

---

## Tech Stack

- **Backend**: FastAPI, Python, Groq API (mixtral-8x7b)
- **Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS
- **Deployment**: Render (backend), Vercel (frontend)
- **Animations**: CSS-only, IntersectionObserver for scroll reveals

---

## The Core Idea

1. **User pastes text** they need to memorize
2. **User picks pattern types** (acronym, acrostic, analogy, number pattern, story/memory palace) OR describes their own custom method
3. **AI generates personalized memory patterns** tuned to the user's preferences
4. **User studies the patterns**, then enters quiz mode
5. **Quiz adapts** — if a pattern type isn't working, the AI switches to a different approach

Built for the Hackathon. Under 12 hours. 🚀