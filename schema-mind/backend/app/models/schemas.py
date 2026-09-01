from pydantic import BaseModel, Field
from typing import List, Optional


# ── Onboarding ──────────────────────────────────────────────────────────

class PatternPreference(BaseModel):
    """A single pattern type preference selected (or custom-described) by the user."""
    type: str = Field(..., description="Built-in type: acronym|acrostic|analogy|number|story OR 'custom'")
    custom_description: Optional[str] = Field(None, description="If type=custom, user's own description")

class OnboardingRequest(BaseModel):
    preferences: List[PatternPreference] = Field(..., min_length=1, max_length=5)

class OnboardingResponse(BaseModel):
    success: bool
    preferences: List[PatternPreference]


# ── Pattern Generation ──────────────────────────────────────────────────

class GeneratePatternsRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=8000, description="The material to memorize")
    preferences: List[PatternPreference] = Field(..., min_length=1, max_length=5)

class GeneratedPattern(BaseModel):
    type: str = Field(..., description="acronym|acrostic|analogy|number|story|custom")
    label: str = Field(..., description="Short human-readable label like 'Acronym: HOMES'")
    content: str = Field(..., description="The full pattern text")

class GeneratePatternsResponse(BaseModel):
    patterns: List[GeneratedPattern]


# ── Quiz Generation ─────────────────────────────────────────────────────

class GenerateQuizRequest(BaseModel):
    patterns: List[GeneratedPattern]
    topic: Optional[str] = Field(None, description="Optional topic summary for context")

class QuizQuestion(BaseModel):
    id: str = Field(..., description="Unique question id")
    type: str = Field(..., description="cloze | multiple_choice")
    pattern_type: str = Field(..., description="Which pattern this tests")
    question: str = Field(..., description="Question text, with blank as ____ for cloze")
    options: Optional[List[str]] = Field(None, description="MCQ options (A/B/C/D)")
    correct_answer: str = Field(..., description="Correct answer text")
    context: Optional[str] = Field(None, description="Optional hint or reference")

class GenerateQuizResponse(BaseModel):
    questions: List[QuizQuestion]


# ── Answer Checking ─────────────────────────────────────────────────────

class CheckAnswerRequest(BaseModel):
    question_id: str
    user_answer: str
    correct_answer: str

class CheckAnswerResponse(BaseModel):
    correct: bool
    explanation: Optional[str] = None


# ── Adaptation ──────────────────────────────────────────────────────────

class AdaptPatternsRequest(BaseModel):
    original_text: str = Field(..., min_length=10, max_length=8000)
    preferences: List[PatternPreference]
    wrong_answers: List[str] = Field(default_factory=list, description="Concepts/questions user got wrong")
    failed_pattern_types: List[str] = Field(default_factory=list, description="Pattern types that aren't sticking")

class AdaptPatternsResponse(BaseModel):
    adapted_patterns: List[GeneratedPattern]
    adaptation_note: str = Field(..., description="Brief explanation of what changed and why")


# ── Health ──────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    model: Optional[str] = None