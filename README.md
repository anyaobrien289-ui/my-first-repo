# Live Discussion Panel

Where inquiry is not constrained by predefined limitations — an open forum for intellectual exploration.

## What you get

- **Live panel**: real-time rooms + messages (Socket.IO).
- **Question explorer**:
  - **Multi-source validation** across **Wikipedia**, **Wikidata**, **OpenAlex**, **Crossref**
  - Cross-verification that highlights overlaps vs single-source signals (to reduce inconsistencies)
- **Deep question generator**:
  - Uses **GPT‑5.2** + **Gemini 3**
  - Returns whether **both models agree** the question is “deep” (backed by both)
- **Surface question generator**:
  - Works without keys
  - Toggle between **Surface/Deep** in the UI

## Run locally

```bash
npm install
npm start
```

### Panel link

Open: `http://localhost:3000/panel`

## Private link (recommended)

Set a token and bind to localhost (not publicly reachable from your network):

```bash
export PANEL_ACCESS_TOKEN="change-me"
export HOST="127.0.0.1"
npm start
```

Open: `http://127.0.0.1:3000/panel?token=change-me`

### If you need a “site link” (remote preview / port forwarding)

To access from outside the machine (preview URL), you must bind to all interfaces:

```bash
export PANEL_ACCESS_TOKEN="change-me"
export HOST="0.0.0.0"
export PORT="3000"
npm start
```

Then use your environment’s forwarded/preview URL and open:

- `https://<your-forwarded-host>/panel?token=change-me`

## Environment variables (for “deep question” backing)

The panel works without any keys for chat + multi-source validation.

To enable deep-question backing, set:

- **`OPENAI_API_KEY`**: required
- **`GEMINI_API_KEY`**: required
- **`OPENAI_MODEL`**: optional (default: `gpt-5.2`)
- **`GEMINI_MODEL`**: optional (default: `gemini-3`)

Example:

```bash
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."
npm start
```
