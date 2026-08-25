from google.generativeai import configure, list_models
import os

configure(api_key=os.environ.get("GEMINI_API_KEY"))
for m in list_models():
    print(m.name)
