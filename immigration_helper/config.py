"""Default locations and models, shared by the command-line entry points. Paths are relative to the project root."""
from pathlib import Path

FORMS_DIR = Path("data/forms")
CHUNKS_PATH = Path("data/index/chunks.jsonl")
VECTOR_INDEX_DIR = Path("data/index/chroma")
EVAL_SET_PATH = Path("data/eval/eval_set.json")
RESULTS_DIR = Path("results")

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4.1-mini"
JUDGE_MODEL = "gpt-4.1"  # stronger than the answering model, so it isn't grading its own work

# Chosen with the answer-level evaluation (README, "Answer-level evaluation").
ANSWER_PASSAGES = 8
FORM_FILTER = True
