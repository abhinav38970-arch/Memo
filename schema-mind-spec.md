# 🧠 SchemaMind — Project Specification

**Tagline:** Paste any text → AI learns how *your* brain works → custom memory patterns → quizzes until it sticks.

---

## 1. Core Loop

```
[User pastes text] → [AI reads preferences] → [Generates personalized patterns]
    → [Shows patterns] → [Quizzes user] → [If failing: adapts + retries]
```

No accounts, no dashboards, no clutter. One focused loop.

---

## 2. User Flow

### Step A: One-Time Preference Onboarding (≈30 seconds)

The user sees a screen asking: **"How does your memory work best?"**

**Option 1 — Pick from built-in types** (check 2–3):

| Pattern Type | What It Means | Example |
|---|---|---|
| **Acronym** | First letters make a word | "HOMES" for the Great Lakes |
| **Acrostic** | First letters make a sentence | "My Very Educated Mother Just Served Us Noodles" for planets |
| **Analogy** | Map the topic onto something familiar | "The immune system is like a castle defense" |
| **Number Pattern** | Associate numbers with items | "3 layers of skin, 4 chambers of the heart..." |
| **Story / Memory Palace** | Weave facts into a narrative | Walk through your house placing facts in rooms |

**Option 2 — Describe your own method** (free text)

If none of the above fit, the user types their own:  
*"I remember things by connecting them to scenes from The Matrix"*  
*"I use football plays as a mental framework for everything"*  
*"I picture the concept as a character in a TV show I like"*

The AI does NOT have a hard block — any pattern type the user can describe, the AI will attempt to generate. If the user's custom method is too vague, the AI asks clarifying questions. If the method doesn't map well to the specific content, the AI suggests blending it with one of the default types.

Stored in `localStorage`. Never asked again unless user wants to update.

### Step B: Paste Text

A clean text area with the prompt: **"Paste the material you need to memorize."**

User pastes anything — a paragraph from a textbook, a list of definitions, a code snippet, etc.

### Step C: AI Generates Custom Patterns

The AI reads the text and generates patterns **using only the user's preferred types**.

Example: User chose *acronym + analogy*.
Input: *"Photosynthesis: Light-dependent reactions use sunlight to produce ATP and NADPH. The Calvin cycle uses ATP and NADPH to fix CO₂ into glucose."*

Output:
- **Acronym:** "L-C-G" → Light → Calvin → Glucose (simplified chain)
- **Analogy:** "Photosynthesis is like a factory assembly line. Sunlight powers the machines (light reactions) which produce fuel (ATP/NADPH) that workers on the second shift (Calvin cycle) use to assemble the final product (glucose)."

### Step D: Quiz Mode

Two quiz types, randomly mixed:

1. **Cloze (fill-in-the-blank):** Parts of the pattern are blanked. User types the missing word.
   - *"Photosynthesis is like a factory ______ line."*

2. **Multiple choice:** Pick the correct completion.
   - *"The Calvin cycle uses ATP and NADPH to fix ___ into glucose."*  A) Oxygen  B) CO₂  C) Water  D) Sunlight

After each answer → immediate correct/incorrect feedback.

### Step E: Adaptation

If the user gets questions wrong:
- If a pattern type isn't working → the AI tries a **different pattern type** for that content.
- If the content itself is being forgotten → the AI **rephrases** the patterns and/or **chunks it smaller**.
- Track what the user misses; bias later quizzes toward weak spots.

---

## 3. Data Model (localStorage)

```json
{
  "preferences": {
    "patternTypes": ["acronym", "analogy", "story"],
    "setupComplete": true
  },
  "sessions": [
    {
      "id": "session-1",
      "inputText": "...",
      "generatedPatterns": { ... },
      "quizResults": [
        { "question": "...", "correct": true, "patternType": "analogy" },
        { "question": "...", "correct": false, "patternType": "acronym" }
      ],
      "adaptations": [
        { "failedType": "acronym", "switchedTo": "story" }
      ],
      "mastered": false
    }
  ]
}
```

No backend, no auth, no database. Everything in browser.

---

## 4. Technical Architecture (< 12h Build)

### Frontend: Single HTML file + vanilla JS + Tailwind (CDN)

- A single `index.html` with embedded CSS and JS.
- No build step, no bundler, no React setup.
- Opens instantly in any browser.

### AI: One API (OpenAI / Anthropic / any LLM)

Three prompts. That's the whole backend.

| Call | What It Does |
|---|---|
| **1. Preference parser** | Store user's chosen pattern types |
| **2. Pattern generator** | Takes text + preferences → returns patterns in structured JSON |
| **3. Quiz generator** | Takes patterns + previous wrong answers → returns cloze + MCQ questions |

All API calls go directly from the frontend (CORS-permissive) or through a tiny serverless proxy. For a hackathon demo, an API key embedded in the frontend (scoped, low-limit) is acceptable.

### Adaptation Logic

Simple decision tree in JS (no ML training needed — the LLM does the heavy lifting):

```
if (wrongAnswer.count[patternType] > 2) {
  switch patternType for this content
}
if (overallScore < 60%) {
  regenerate patterns with "simpler language" flag
}
if (specific concept missed repeatedly) {
  add concept to "focus list" for quiz bias
}
```

---

## 5. State Machine (UI)

```
WELCOME → ONBOARDING (if no prefs) → PASTE_INPUT
    → GENERATING (loading spinner) → PATTERNS_VIEW
        → QUIZ → RESULTS → [ADAPT / RETRY / DONE]
```

Four screens total. Each screen is a div that shows/hides.

---

## 6. Build Roadmap (for < 12 Hours)

| Phase | Time | Deliverable |
|---|---|---|
| **Phase 1: Core shell** | 2h | Single HTML page with all 4 screens (Welcome, Paste, Patterns, Quiz) and state machine |
| **Phase 2: Pattern generation** | 2h | Wire up the LLM prompt for generating patterns from pasted text + user prefs |
| **Phase 3: Quiz engine** | 2h | Cloze + MCQ question generation, answer checking, scoring |
| **Phase 4: Adaptation loop** | 1.5h | Track results per pattern type, auto-switch when something isn't sticking |
| **Phase 5: Polish** | 1.5h | Animations, error states, demo data pre-loaded (so you're not typing live), README |
| **Buffer** | 2h | Unexpected issues, practice demo run-through |

---

## 7. What Makes This "AI/ML" (Judge-Proof Answer)

When a judge asks *"where's the AI?"*:

> **"Three parts. First, an LLM extracts the semantic structure of the pasted text and transforms it into memory patterns tuned to the user's learning style — that's the AI generation. Second, a quiz engine tests recall and tracks which pattern types work per user. Third, an adaptation layer detects when a pattern isn't sticking and dynamically switches strategies — that's the ML feedback loop. The more the user studies, the better the system learns how they learn."**

No one expects a trained neural network at a 12-hour hackathon. A smart LLM pipeline + adaptation logic is well within the theme.

---

## 8. One-Liner Pitch (15 Seconds)

> *"SchemaMind is like a personal tutor who figures out exactly how your memory works — acronyms, stories, analogies, whatever clicks for you — then rewrites any material into that format and quizzes you until you can't forget it."*

---

*Built for [Hackathon Name] | Category: AI/ML for Education*