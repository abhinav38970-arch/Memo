"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

/* ── Types ── */
interface PatternPref {
  type: string;
  custom_description?: string;
}

interface Pattern {
  type: string;
  label: string;
  content: string;
}

interface Question {
  id: string;
  type: "cloze" | "multiple_choice";
  pattern_type: string;
  question: string;
  options?: string[];
  correct_answer: string;
}

/* ── API config ── */
// Relative by default: Next.js rewrites /api/* to the backend (see next.config.mjs).
// Set NEXT_PUBLIC_API_URL only if the browser should hit the backend directly.
// Trailing slashes are stripped so "https://x.onrender.com/" doesn't produce "//api/..." (404s).
const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

/* ── Extract a useful error message from a failed API response ── */
async function apiError(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail);
    if (detail) return new Error(`API error ${res.status}: ${detail}`);
  } catch {
    /* body wasn't JSON */
  }
  return new Error(`API error: ${res.status}`);
}

/* ── Built-in pattern types ── */
const BUILTIN_TYPES = [
  { id: "acronym", label: "Acronym", desc: "First letters make a word (e.g. HOMES for Great Lakes)" },
  { id: "acrostic", label: "Acrostic", desc: "First letters make a sentence (e.g. My Very Educated Mother...)" },
  { id: "analogy", label: "Analogy", desc: "Map topic onto something familiar (e.g. immune system = castle)" },
  { id: "number", label: "Number Pattern", desc: "Associate numbers with concepts (e.g. 4 chambers of heart)" },
  { id: "story", label: "Story / Memory Palace", desc: "Weave facts into a narrative or walk through a familiar place" },
];

/* ── Steps ── */
type Step = "onboarding" | "input" | "generating" | "patterns" | "quiz" | "results" | "adapting";

export default function ToolPage() {
  /* ── State ── */
  const [step, setStep] = useState<Step>("onboarding");
  const [preferences, setPreferences] = useState<PatternPref[]>([]);
  const [customDesc, setCustomDesc] = useState("");
  const [inputText, setInputText] = useState("");
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [userAnswer, setUserAnswer] = useState("");
  const [answers, setAnswers] = useState<{ qid: string; correct: boolean; answer: string }[]>([]);
  const [wrongConcepts, setWrongConcepts] = useState<string[]>([]);
  const [failedTypes, setFailedTypes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState<{ show: boolean; correct: boolean; expected: string }>({ show: false, correct: false, expected: "" });
  const [quizDone, setQuizDone] = useState(false);
  const [adaptNote, setAdaptNote] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [onboardMode, setOnboardMode] = useState<"pick" | "custom">("pick");

  /* ── Onboarding: toggle built-in type ── */
  function toggleBuiltin(id: string) {
    setPreferences((prev) => {
      const exists = prev.find((p) => p.type === id);
      if (exists) return prev.filter((p) => p.type !== id);
      return [...prev, { type: id }];
    });
  }

  /* ── Onboarding: add custom ── */
  function addCustom() {
    const desc = customDesc.trim();
    if (!desc) return;
    setPreferences((prev) => [...prev, { type: "custom", custom_description: desc }]);
    setCustomDesc("");
  }

  /* ── API calls ── */
  const generatePatterns = useCallback(async () => {
    if (!inputText.trim() || preferences.length === 0) return;
    setLoading(true);
    setError("");
    setStep("generating");
    try {
      const res = await fetch(`${API_BASE}/api/generate-patterns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: inputText, preferences }),
      });
      if (!res.ok) throw await apiError(res);
      const data = await res.json();
      setPatterns(data.patterns);
      setStep("patterns");
    } catch (e: any) {
      setError(e.message || "Failed to generate patterns");
      setStep("input");
    } finally {
      setLoading(false);
    }
  }, [inputText, preferences]);

  const generateQuiz = useCallback(async () => {
    if (patterns.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/generate-quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patterns }),
      });
      if (!res.ok) throw await apiError(res);
      const data = await res.json();
      setQuestions(data.questions);
      setCurrentQ(0);
      setAnswers([]);
      setQuizDone(false);
      setStep("quiz");
    } catch (e: any) {
      setError(e.message || "Failed to generate quiz");
    } finally {
      setLoading(false);
    }
  }, [patterns]);

  const adaptPatterns = useCallback(async () => {
    if (!inputText.trim() || preferences.length === 0) return;
    setLoading(true);
    setError("");
    setStep("adapting");
    try {
      const res = await fetch(`${API_BASE}/api/adapt-patterns`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          original_text: inputText,
          preferences,
          wrong_answers: wrongConcepts,
          failed_pattern_types: failedTypes,
        }),
      });
      if (!res.ok) throw await apiError(res);
      const data = await res.json();
      setPatterns(data.adapted_patterns);
      setAdaptNote(data.adaptation_note);
      setStep("patterns");
    } catch (e: any) {
      setError(e.message || "Failed to adapt patterns");
      setStep("results");
    } finally {
      setLoading(false);
    }
  }, [inputText, preferences, wrongConcepts, failedTypes]);

  /* ── Quiz answer handling ── */
  function submitAnswer() {
    if (!userAnswer.trim() || questions.length === 0) return;
    const q = questions[currentQ];
    const correct = userAnswer.trim().toLowerCase() === q.correct_answer.toLowerCase();
    setAnswers((prev) => [...prev, { qid: q.id, correct, answer: userAnswer }]);
    setFeedback({ show: true, correct, expected: q.correct_answer });
    if (!correct) {
      setWrongConcepts((prev) => prev.includes(q.pattern_type) ? prev : [...prev, q.pattern_type]);
      // Track which pattern type failed
      setFailedTypes((prev) => prev.includes(q.pattern_type) ? prev : [...prev, q.pattern_type]);
    }
  }

  function nextQuestion() {
    setFeedback({ show: false, correct: false, expected: "" });
    setUserAnswer("");
    if (currentQ + 1 >= questions.length) {
      setQuizDone(true);
      const score = answers.filter((a) => a.correct).length;
      if (score < questions.length * 0.6) {
        setStep("results");
      } else {
        setStep("results");
      }
    } else {
      setCurrentQ((prev) => prev + 1);
    }
  }

  function handleMCQ(option: string) {
    // Extract just the text after "A) ", "B) ", etc.
    const answerText = option.replace(/^[A-D]\)\s*/, "");
    setUserAnswer(answerText);
  }

  /* ── Score calculation ── */
  const score = answers.filter((a) => a.correct).length;
  const total = answers.length;
  const pct = total > 0 ? Math.round((score / total) * 100) : 0;

  /* ── Reset all ── */
  function resetAll() {
    setStep("onboarding");
    setPreferences([]);
    setInputText("");
    setPatterns([]);
    setQuestions([]);
    setCurrentQ(0);
    setUserAnswer("");
    setAnswers([]);
    setWrongConcepts([]);
    setFailedTypes([]);
    setError("");
    setFeedback({ show: false, correct: false, expected: "" });
    setQuizDone(false);
    setAdaptNote("");
  }

  /* ── Render ── */
  return (
    <main className="relative min-h-screen">
      {/* Small header for tool page */}
      <header className="flex items-center justify-between px-4 py-3 md:px-8 max-w-6xl mx-auto">
        <Link href="/" className="flex items-center gap-2">
          <div className="w-8 h-8 md:w-10 md:h-10 rounded-full bg-white flex items-center justify-center">
            <svg width="60%" height="60%" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#111" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="font-display text-white text-sm hidden sm:inline">SchemaMind</span>
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-[#b4b4b4] text-xs md:text-sm">
            Step {step === "onboarding" ? "1" : step === "input" ? "2" : step === "patterns" ? "3" : step === "quiz" ? "4" : "5"}/5
          </span>
          <Link href="/" className="text-[#e2e2e2] text-xs md:text-sm hover:text-white transition-colors">
            Back to Home
          </Link>
        </div>
      </header>

      {/* ── Main content ── */}
      <div className="max-w-4xl mx-auto px-4 py-4 md:py-8">
        {/* ── STEP 1: ONBOARDING ── */}
        {step === "onboarding" && (
          <div className="space-y-8">
            <div className="text-center anim in-view">
              <h1 className="headline text-3xl md:text-5xl mb-3">
                <span className="headline-line block">How does YOUR</span>
                <span className="headline-line block">memory work best?</span>
              </h1>
              <p className="text-[#eaeaea] text-sm md:text-base max-w-xl mx-auto text-on-video">
                Pick the patterns that click with you. Or describe your own method — anything goes.
              </p>
            </div>

            {/* Toggle: Pick / Custom */}
            <div className="flex justify-center gap-4">
              <button
                onClick={() => setOnboardMode("pick")}
                className={`px-6 py-2 rounded-full text-sm font-medium transition-all ${
                  onboardMode === "pick"
                    ? "bg-white text-black"
                    : "bg-[#28282a] text-[#e2e2e2] hover:bg-[#323234]"
                }`}
              >
                Pick from list
              </button>
              <button
                onClick={() => setOnboardMode("custom")}
                className={`px-6 py-2 rounded-full text-sm font-medium transition-all ${
                  onboardMode === "custom"
                    ? "bg-white text-black"
                    : "bg-[#28282a] text-[#e2e2e2] hover:bg-[#323234]"
                }`}
              >
                Describe my own
              </button>
            </div>

            {/* Pick mode */}
            {onboardMode === "pick" && (
              <div className="grid md:grid-cols-2 gap-3 max-w-2xl mx-auto">
                {BUILTIN_TYPES.map((t) => {
                  const selected = preferences.find((p) => p.type === t.id);
                  return (
                    <button
                      key={t.id}
                      onClick={() => toggleBuiltin(t.id)}
                      className={`text-left p-4 rounded-xl border transition-all ${
                        selected
                          ? "bg-white/10 border-white/40"
                          : "bg-white/5 border-white/10 hover:bg-white/10 hover:border-white/30"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                            selected ? "border-white bg-white" : "border-white/40"
                          }`}
                        >
                          {selected && <div className="w-2.5 h-2.5 rounded-full bg-black" />}
                        </div>
                        <div>
                          <div className="text-white font-medium text-sm">{t.label}</div>
                          <div className="text-[#b4b4b4] text-xs">{t.desc}</div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}

            {/* Custom mode */}
            {onboardMode === "custom" && (
              <div className="max-w-xl mx-auto space-y-4">
                <p className="text-[#e2e2e2] text-sm text-on-video">
                  Tell us how you remember things. Any method works —{" "}
                  <span className="italic">"I connect stuff to scenes from The Matrix"</span>,{" "}
                  <span className="italic">"I use football plays"</span>,{" "}
                  <span className="italic">"I imagine concepts as characters in a TV show"</span>.
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={customDesc}
                    onChange={(e) => setCustomDesc(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && addCustom()}
                    placeholder="Describe your memory method..."
                    className="flex-1 bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder:text-[#b4b4b4] text-sm focus:outline-none focus:border-white/40"
                  />
                  <button
                    onClick={addCustom}
                    disabled={!customDesc.trim()}
                    className="bg-white text-black px-5 py-3 rounded-xl font-medium text-sm disabled:opacity-50 hover:bg-white/90 transition-all"
                  >
                    Add
                  </button>
                </div>
                {/* Show added customs */}
                {preferences.filter((p) => p.type === "custom").length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[#b4b4b4] text-xs font-medium uppercase tracking-wider">Your custom methods:</p>
                    {preferences.filter((p) => p.type === "custom").map((p, i) => (
                      <div key={i} className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
                        <span className="text-white text-sm flex-1">{p.custom_description}</span>
                        <button
                          onClick={() => setPreferences((prev) => prev.filter((_, idx) => idx !== i))}
                          className="text-[#b4b4b4] hover:text-white text-sm"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Selected preferences summary */}
            {preferences.length > 0 && (
              <div className="text-center">
                <div className="inline-flex flex-wrap gap-2 justify-center mb-6">
                  {preferences.map((p, i) => (
                    <span key={i} className="bg-white/10 border border-white/20 rounded-full px-3 py-1 text-xs text-white">
                      {p.type === "custom" ? p.custom_description : p.type}
                    </span>
                  ))}
                </div>
                <button
                  onClick={() => setStep("input")}
                  className="bg-white text-black px-8 py-3 rounded-full font-semibold text-sm hover:scale-105 transition-all cta-glow"
                >
                  Continue  →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── STEP 2: INPUT ── */}
        {step === "input" && (
          <div className="space-y-8 max-w-2xl mx-auto">
            <div className="text-center anim in-view">
              <h2 className="headline text-2xl md:text-4xl mb-2">Paste your material</h2>
              <p className="text-[#eaeaea] text-sm text-on-video">
                Paste the text you need to memorize. Anything from a textbook paragraph to code docs.
              </p>
            </div>

            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Paste your text here..."
              rows={10}
              className="w-full bg-white/10 border border-white/20 rounded-2xl px-5 py-4 text-white placeholder:text-[#b4b4b4] text-sm focus:outline-none focus:border-white/40 resize-y min-h-[200px]"
            />

            <div className="flex justify-between items-center">
              <button
                onClick={() => setStep("onboarding")}
                className="text-[#b4b4b4] hover:text-white text-sm transition-colors"
              >
                ← Change preferences
              </button>
              <button
                onClick={generatePatterns}
                disabled={!inputText.trim()}
                className="bg-white text-black px-8 py-3 rounded-full font-semibold text-sm hover:scale-105 transition-all cta-glow disabled:opacity-50 disabled:hover:scale-100"
              >
                Generate Patterns →
              </button>
            </div>

            {error && <p className="text-red-400 text-sm text-center">{error}</p>}
          </div>
        )}

        {/* ── STEP 3: GENERATING / ADAPTING ── */}
        {(step === "generating" || step === "adapting") && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="w-12 h-12 border-2 border-white/30 border-t-white rounded-full animate-spin mb-6" />
            <p className="text-white font-medium">
              {step === "generating" ? "Crafting your memory patterns..." : "Adapting patterns based on your progress..."}
            </p>
            <p className="text-[#b4b4b4] text-sm mt-2 text-on-video">This takes a few seconds</p>
          </div>
        )}

        {/* ── STEP 4: PATTERNS VIEW ── */}
        {step === "patterns" && (
          <div className="space-y-8">
            <div className="text-center anim in-view">
              <h2 className="headline text-2xl md:text-4xl mb-2">Your Memory Patterns</h2>
              <p className="text-[#eaeaea] text-sm max-w-xl mx-auto text-on-video">
                {adaptNote ? adaptNote : "Here are your personalized patterns. Study them, then test yourself."}
              </p>
            </div>

            <div className="space-y-4">
              {patterns.map((p, i) => (
                <div
                  key={i}
                  className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-5 md:p-6 anim"
                  style={{ animationDelay: `${0.2 + i * 0.1}s` }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[#b4b4b4] text-xs font-medium uppercase tracking-wider bg-white/10 px-2 py-0.5 rounded-full">
                      {p.type}
                    </span>
                    <span className="text-white font-medium text-sm">{p.label}</span>
                  </div>
                  <p className="text-[#e2e2e2] text-sm leading-relaxed whitespace-pre-wrap">{p.content}</p>
                </div>
              ))}
            </div>

            <div className="flex justify-center gap-4">
              <button
                onClick={generateQuiz}
                disabled={loading}
                className="bg-white text-black px-8 py-3 rounded-full font-semibold text-sm hover:scale-105 transition-all cta-glow disabled:opacity-50"
              >
                {loading ? "Generating quiz..." : "Test Yourself →"}
              </button>
              <button
                onClick={resetAll}
                className="text-[#b4b4b4] hover:text-white text-sm transition-colors px-4"
              >
                Start Over
              </button>
            </div>

            {error && <p className="text-red-400 text-sm text-center">{error}</p>}
          </div>
        )}

        {/* ── STEP 5: QUIZ ── */}
        {step === "quiz" && !quizDone && questions.length > 0 && (
          <div className="space-y-8 max-w-2xl mx-auto">
            {/* Progress bar */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-white rounded-full transition-all duration-300"
                  style={{ width: `${((currentQ) / questions.length) * 100}%` }}
                />
              </div>
              <span className="text-[#b4b4b4] text-xs">
                {currentQ + 1}/{questions.length}
              </span>
            </div>

            {/* Question */}
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 md:p-8 anim in-view">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[#b4b4b4] text-xs font-medium uppercase tracking-wider">
                  {questions[currentQ].type === "cloze" ? "Fill in the blank" : "Multiple Choice"}
                </span>
                <span className="text-[#b4b4b4] text-xs">
                  · {questions[currentQ].pattern_type}
                </span>
              </div>

              <p className="text-white text-base md:text-lg font-medium mb-6 leading-relaxed">
                {questions[currentQ].question}
              </p>

              {/* MCQ options */}
              {questions[currentQ].type === "multiple_choice" && questions[currentQ].options && (
                <div className="space-y-2 mb-4">
                  {questions[currentQ].options!.map((opt, i) => (
                    <button
                      key={i}
                      onClick={() => handleMCQ(opt)}
                      disabled={feedback.show}
                      className={`w-full text-left p-3 rounded-xl border text-sm transition-all ${
                        userAnswer === opt.replace(/^[A-D]\)\s*/, "")
                          ? "bg-white/15 border-white/40 text-white"
                          : "bg-white/5 border-white/10 hover:bg-white/10 text-[#e2e2e2]"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}

              {/* Cloze input */}
              {questions[currentQ].type === "cloze" && (
                <div className="mb-4">
                  <input
                    type="text"
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && !feedback.show && submitAnswer()}
                    placeholder="Type your answer..."
                    disabled={feedback.show}
                    className="w-full bg-white/10 border border-white/20 rounded-xl px-4 py-3 text-white placeholder:text-[#b4b4b4] text-sm focus:outline-none focus:border-white/40"
                  />
                </div>
              )}

              {/* Submit / Next buttons */}
              <div className="flex gap-3">
                {!feedback.show ? (
                  <button
                    onClick={submitAnswer}
                    disabled={!userAnswer.trim()}
                    className="bg-white text-black px-6 py-2.5 rounded-full font-medium text-sm disabled:opacity-50 hover:scale-105 transition-all"
                  >
                    Submit Answer
                  </button>
                ) : (
                  <>
                    <div className={`px-4 py-2.5 rounded-xl text-sm font-medium ${
                      feedback.correct
                        ? "bg-green-500/20 text-green-300"
                        : "bg-red-500/20 text-red-300"
                    }`}>
                      {feedback.correct ? "✓ Correct!" : `✗ Wrong. Answer: ${feedback.expected}`}
                    </div>
                    <button
                      onClick={nextQuestion}
                      className="bg-white text-black px-6 py-2.5 rounded-full font-medium text-sm hover:scale-105 transition-all"
                    >
                      {currentQ + 1 >= questions.length ? "See Results" : "Next →"}
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── RESULTS ── */}
        {step === "results" && (
          <div className="space-y-8 max-w-2xl mx-auto text-center">
            <div className="anim in-view">
              <h2 className="headline text-3xl md:text-5xl mb-2">
                {pct >= 80 ? "Nice work!" : pct >= 60 ? "Getting there!" : "Let's try again"}
              </h2>
              <div className="text-6xl md:text-8xl font-display text-white mt-4 mb-2">
                {pct}%
              </div>
              <p className="text-[#e2e2e2] text-on-video">
                {score}/{total} correct
              </p>
            </div>

            {pct < 80 && (
              <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 anim" style={{ animationDelay: "0.2s" }}>
                <h3 className="text-white font-medium mb-2">Pattern types that need work:</h3>
                <div className="flex flex-wrap gap-2 justify-center mt-2">
                  {failedTypes.filter((t, i, a) => a.indexOf(t) === i).map((t, i) => (
                    <span key={i} className="bg-red-500/20 border border-red-500/30 rounded-full px-3 py-1 text-xs text-red-300">
                      {t}
                    </span>
                  ))}
                </div>
                <button
                  onClick={adaptPatterns}
                  className="mt-6 bg-white text-black px-8 py-3 rounded-full font-semibold text-sm hover:scale-105 transition-all cta-glow"
                >
                  Try Different Approach →
                </button>
              </div>
            )}

            <div className="flex justify-center gap-4 mt-4">
              {pct >= 80 && (
                <button
                  onClick={() => { setStep("input"); setQuestions([]); setAnswers([]); setQuizDone(false); }}
                  className="bg-white text-black px-8 py-3 rounded-full font-semibold text-sm hover:scale-105 transition-all"
                >
                  Study Something Else →
                </button>
              )}
              <button
                onClick={resetAll}
                className="text-[#b4b4b4] hover:text-white text-sm transition-colors px-4"
              >
                Start Over
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <footer className="py-8 px-4 text-center border-t border-white/10 mt-8">
        <p className="text-[#b4b4b4] text-xs">
          SchemaMind — Paste. Learn. Remember. Built for the Hackathon.
        </p>
      </footer>
    </main>
  );
}