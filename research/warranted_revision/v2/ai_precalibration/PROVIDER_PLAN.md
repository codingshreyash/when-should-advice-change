# Plan: a second-provider annotator (not run; needs approval)

**Why.** Annotators A and B are both Claude models. Agreement between models from different
providers says more, because their training and blind spots overlap less. It still isn't
human validation.

**What would run.** The same blinded packet, with the same `GUIDELINES.md` as the system
instructions, sent to one model from another provider (for example a current GPT or Gemini
model). It would be one request per item, at temperature 0, with the reply parsed into the
packet's CSV columns. The output goes to `annotations/annotator_C/`, and agreement with A and B
is reported pairwise and as three-rater α. Nothing else changes.

**Size and cost.**

- 48 item requests of about 3,000 input tokens each (guidelines, scenario and follow-up) and
  about 250 output tokens.
- Plus 11 base-check requests.
- Total: about 180k input and 15k output tokens.
- At list prices of a few dollars per million input tokens this is well under $2, but the exact
  price must be read from the provider's pricing page before running.
- **Proposed cap: $5**, enforced by stopping at a fixed request count (59) and a token budget.

**What it needs from you.**

1. Approval to spend.
2. An API key, stored as an environment secret (never pasted into chat).
3. Network access to that provider's API host from this environment, which may need an
   environment network-policy change.

**Stop conditions.**

- Any request error rate above 5% means stop.
- A reply that can't be parsed into a valid label is recorded as missing, not retried until it
  agrees.
