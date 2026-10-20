# AI experiment suggestions

The third dashboard card sends an experiment goal and the selected model's training
settings to the OpenAI Responses API. It displays draft suggestions and Python code.
Generating a suggestion does not run training, change a model, or write a database record.
With no selected version, it summarizes at most the three newest versions.

## Setup

Install `backend/requirements.txt`. Add these values to your existing `backend/.env`
for local development, or to the Render service's environment variables for the live app:

```text
OPENAI_API_KEY=your-actual-openai-api-key
OPENAI_MODEL=gpt-5.4-mini
MLFLOWPRO_AI_ACCESS_CODE=your-private-team-access-code
```

Generate a random team access code if needed:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

Restart Django after local environment changes. Use the access code in the dashboard
form; the OpenAI API key stays on the server. Keep `backend/.env` out of Git.
The model is configurable to support models available to your API account.
An API key with access to the configured model and available API credit is required.

## Demo

1. Choose an existing model version in the review card.
2. Scroll to **AI Experiment Suggestions** and enter the team access code.
3. Ask: “Suggest two Logistic Regression C values and explain how to compare them.”
4. Generate suggestions. Explain the rationale and review the Python snippet.
5. Compare candidates using cross-validation on the training split before deciding
   what to train. Report new scores only after running and recording an experiment.

## Implementation and limits

- `POST /api/ai-suggestions/` accepts `goal` and optional `version_id`.
- A private team code is required in `X-MLFlowPro-Access-Code`.
- The server sends model settings and previous training CV scores; it omits held-out
  test scores, raw reviews, artifact paths, and environment variables.
- Requests allow at most 1,200 goal characters, 1,400 output tokens, no automatic
  retries, and a 20-second SDK timeout. A cache throttle permits five calls/minute
  per Django cache instance; this is not a project-wide spending limit.
- The API request uses `store=False` and no tools. The browser renders output as text.
- The code can be wrong. This feature provides drafts for human review.
- The team code protects this demo feature; it is not OAuth2 or enterprise identity.
- Automated tests simulate provider responses, including a real SDK/mock HTTP test.
  They do not confirm the project's real API key, billing, model access, or output quality.

## Official API references

- https://developers.openai.com/api/docs/quickstart
- https://developers.openai.com/api/reference/python/resources/responses/methods/create
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
