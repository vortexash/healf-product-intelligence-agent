# Deployment - Backend on Render, Frontend on Vercel

Two free services. **Deploy the backend first** (the frontend needs its URL). ~10 minutes.

Repo: `https://github.com/vortexash/healf-product-intelligence-agent`

---

## Step 1 - Backend on Render

1. Go to **https://render.com** → sign in with GitHub.
2. **New +  →  Blueprint** → select the `healf-product-intelligence-agent` repo.
   Render reads **`render.yaml`** and proposes a `healf-backend` Docker web service (root: `backend`).
3. Before/after first deploy, open the service → **Environment** and set the secret:
   - `OPENAI_API_KEY` = *your key* (the value from your local `backend/.env`).
   - (`LLM_PROVIDER=openai`, `OPENAI_MODEL=gpt-4o`, `FRONTEND_ORIGIN=*` come from `render.yaml`.)
4. **Deploy**. When it's live, copy the URL, e.g. `https://healf-backend.onrender.com`.
5. **Verify:** open `https://healf-backend.onrender.com/health` → `{"status":"ok","llm_configured":true}`.

> ⚠️ **Render free tier sleeps after ~15 min idle**, so the *first* request after a pause takes
> ~30-60s (cold start). Tell the interviewer to give the first message a moment. Everything after is fast.

---

## Step 2 - Frontend on Vercel

1. Go to **https://vercel.com** → sign in with GitHub → **Add New… → Project** → import the same repo.
2. **Set Root Directory = `frontend`** (important - the repo is a monorepo). Framework auto-detects as Next.js.
3. Add an **Environment Variable**:
   - `NEXT_PUBLIC_API_BASE_URL` = your Render backend URL from Step 1 (no trailing slash),
     e.g. `https://healf-backend.onrender.com`
4. **Deploy**. Copy the Vercel URL, e.g. `https://healf-product-intelligence-agent.vercel.app`.

---

## Step 3 - (optional) tighten CORS

The backend ships with `FRONTEND_ORIGIN=*` so it works immediately. To lock it to your frontend:
in Render → Environment → set `FRONTEND_ORIGIN` = your Vercel URL → save (redeploys).

---

## Step 4 - Send the interviewer

Send the **Vercel URL**. They paste a Healf product URL and ask a question - no setup on their side.

Suggested test to include in your message:
```
https://healf.com/en-uk/products/lmnt-recharge-electrolytes-variety-pack
Does this contain Vitamin D?   →  then: "What can I improve on this page?"
```

---

## Cost & safety notes

- The hosted app uses **your OpenAI key**. Factual answers (reviews, ingredients, price) use **no LLM**;
  only page-evaluation and content-rewrite call it. Set a **usage limit** in the OpenAI dashboard, and
  consider rotating/disabling the key after the interview.
- The key lives **only** in the host's env vars and your local `.env` - never in the repo.
- The backend only fetches `healf.com` (SSRF-guarded) and never exposes a generic fetch endpoint.

## Alternative: no hosting

The interviewer can also run it locally with zero accounts:
```bash
git clone https://github.com/vortexash/healf-product-intelligence-agent
cd healf-product-intelligence-agent
cp backend/.env.example backend/.env   # add an OPENAI or ANTHROPIC key (optional)
docker compose up --build              # frontend :3000 · backend :8000
```
