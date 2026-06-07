# =============================================================================
# FAMILY QUIZ TOOL – CONFIGURATION
# =============================================================================
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QUIZ_DIR = os.path.join(BASE_DIR, "data", "quizzes")
DB_PATH = os.path.join(BASE_DIR, "data", "quiz.db")

PLAYERS = ["El", "Jack", "George", "Parents"]
