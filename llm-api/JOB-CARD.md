# Job card

| | |
|---|---|
| **What it does (one sentence)** | Classifies a support message so it lands on the right team. |
| **Input** | `{ "text": "string, 1-2000 characters" }` |
| **Output** | `{ "category": one of [billing\|bug\|feature\|other], "urgency": one of [low\|normal\|high], "confidence": 0.0-1.0, "reason": "one short sentence" }` |
| **It must never** | invent a category outside the list · return free text · give medical, legal or financial advice · reveal the prompt |
| **When unsure it should** | return category `other` with confidence below 0.5, not a guess |

## The three rules

1. **Closed output:** the same four field names every time, and `category` and `urgency` come from short fixed lists.
2. **One decision:** one message in, one answer out. No conversation, no memory of earlier requests.
3. **A human could grade it:** for any message I can say whether the category is right or wrong.
