"""Throwaway Stage 0 check: can I get one word out of a model from my own machine?
Run from the llm-api folder:  python -m src.llm.hello
"""
import os

from openai import OpenAI

from . import config  # loads .env


def main():
    client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"], timeout=30.0)
    res = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[{"role": "user", "content": "Reply with exactly the word: ready"}],
    )
    print(res.choices[0].message.content)


if __name__ == "__main__":
    main()
