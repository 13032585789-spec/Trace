"""python -m agent.list_models  -> prints the Gemini model names your key can use."""
from .agent import list_models

if __name__ == "__main__":
    list_models()
