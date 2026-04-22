# AI Music Copilot — Architecture

## 🧠 Overview

This system converts a YouTube song into structured musical data (key, BPM, chords, etc.).

---

## 🧱 Core Components

### 1. Mobile App (Frontend)

* Built with React Native (Expo)
* Handles user input and display
* Sends requests to backend

---

### 2. Python Backend (FastAPI)

* Entry point: `main.py`
* Handles API requests
* Orchestrates pipeline execution

---

### 3. Music Engine (Core Intelligence)

Located in:

```
app/services/
```

Includes:

* `pipeline.py` → orchestration
* `analysis.py` → music logic
* `render.py`, `separation.py` → output generation

---

### 4. Job System (Async Processing)

Endpoints:

* `POST /api/jobs`
* `GET /api/jobs/{job_id}`

Flow:

1. Create job
2. Run pipeline in background
3. Store result
4. Retrieve result later

---

### 5. Database (Planned — Supabase)

* Will store:

  * analyzed songs
  * cached results
  * user data

---

## ⚙️ Current API Strategy (MVP)

### Blocking Endpoint (Option A)

```
POST /analyze-song-simple
```

* Calls job system internally
* Waits for completion
* Returns final result directly

✅ Pros:

* Simple integration with mobile app
* Faster development

❌ Cons:

* Not scalable for long-running jobs

---

## 🔁 Future Upgrade (IMPORTANT)

### Async Job System (Option B)

We will return to:

```
POST /api/jobs
GET /api/jobs/{job_id}
```

When:

* scaling users
* handling long jobs
* optimizing performance

⚠️ This is REQUIRED for production scale.

---

## 🧠 Design Principles

* Keep intelligence in Python (core advantage)
* Keep frontend simple
* Separate:

  * UI
  * logic
  * storage
* Prefer caching over recomputation

---

## 🚀 Next Steps

1. Add blocking API wrapper
2. Connect mobile app
3. Add caching (Supabase)
4. Improve analysis accuracy

---

# 🚀 Roadmap / Future Work

## Phase B — Output Quality (CURRENT FOCUS)
- [ ] Clean chord progression (remove noise, stabilize)
- [ ] Detect repeating chord loop
- [ ] Group chords into bars/measures
- [ ] Improve chord confidence filtering

## Phase C — Musical Intelligence
- [ ] Section detection (verse / chorus / bridge)
- [ ] Strumming pattern estimation
- [ ] Rhythm / groove suggestions
- [ ] Difficulty rating for learners

## Phase D — Core Differentiator
- [ ] Merge best analysis logic (Replit vs Web MVP)
- [ ] Improve chord accuracy model
- [ ] Smarter key detection corrections

## Phase E — Backing Track System
- [ ] Integrate backing track generation into current pipeline
- [ ] Sync backing track with detected tempo + key
- [ ] Allow instrument selection (drums, bass, etc.)
- [ ] Loop sections for practice

## Phase F — UX / Product
- [ ] Clean mobile UI (cards, spacing, hierarchy)
- [ ] Display chord chart (bars instead of timestamps)
- [ ] Save past analyses
- [ ] Offline mode (later)

## Phase G — Scaling (IMPORTANT)
- [ ] Reintroduce async job system (Option B)
- [ ] Move to cloud backend
- [ ] Add database (Supabase or similar)
- [ ] Handle large audio jobs reliably

## Tech Debt / Infra
- [ ] Remove hardcoded IP (use env config)
- [ ] Add error handling in frontend
- [ ] Add loading states + retries

-------