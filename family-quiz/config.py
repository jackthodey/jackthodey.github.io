# =============================================================================
# FAMILY QUIZ TOOL – CONFIGURATION
# =============================================================================
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "data", "quiz.db")

PLAYERS = ["El", "Jack", "George", "Parents"]

# Default number of questions in a week's quiz. Players mark each one
# right or wrong themselves (the quiz content lives on paper, not here).
QUESTION_COUNT = 25
