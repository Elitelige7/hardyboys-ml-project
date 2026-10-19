# Real-time experiment notes

The fourth dashboard card lets team members share experiment planning notes.
A save is broadcast over WebSockets to other connected tabs. The database stores
the note and its revision so it can be recovered after reconnecting.

## Local setup and demo

1. Install `backend/requirements.txt` and run migrations.
2. Set `MLFLOWPRO_AI_ACCESS_CODE` in the existing `backend/.env`. This is the team's
   own private access code, which also protects the AI suggestion form; API credit
   is not needed for collaboration.
3. Start `python backend/manage.py runserver` or `python run_asgi.py` from the root.
4. Open the dashboard in two tabs. In each tab, scroll to **Shared Experiment Notes**,
   enter the team code, and click **Connect**.
5. Edit the note in one tab and click **Save Notes**. The other tab receives it.
6. To demonstrate conflict handling, type different drafts in both tabs, save one,
   then try saving the other. The stale draft must not overwrite the newer note.
   Copy your unsaved draft before choosing **Load Latest Notes**.

These are shared planning notes, not automatic edits to trained models or a
character-by-character document editor. A change is shared when a person saves it.

## Render deployment

Commit the generated migration along with the application files. The existing
build script already runs migrations. Set the Render **Start Command** to:

```text
python run_asgi.py
```

Configure `MLFLOWPRO_AI_ACCESS_CODE` in the Render service environment too.
The existing `RENDER_EXTERNAL_HOSTNAME` handling must remain in Django settings.
The browser uses `wss://` on the HTTPS live site and `ws://` locally.
The new start script runs a single Daphne process for both HTTP and WebSockets.
The Docker startup script is updated to call this same server.

## Protocol and concurrency

- WebSocket path: `/ws/experiment-notes/`.
- The first JSON message authenticates with the team code. The code is not put in
  the URL or broadcast to other clients. Browser origins are checked by Channels.
- Messages are `authenticate`, `load`, `save`, or `ping`.
- `save` includes a body of at most 4,000 characters and the revision that was edited.
- The server compares and increments the stored revision in an atomic update.
  A stale revision receives a conflict response instead of overwriting newer data.
- A successful save increments the revision and broadcasts the stored note.
- An incoming update does not replace an unsaved local draft.
- Saved notes persist in the configured database. Local SQLite data stays on that
  machine; the live PostgreSQL database is separate.

## Deployment limit

The in-memory channel layer supports this single-process class demo. Multiple
server processes or instances require a shared channel layer such as Redis.
This implementation does not claim distributed collaboration, CRDT editing,
per-user attribution, or OAuth2 identity. Team-code access is the current boundary.

## Validation

WebSocket tests cover two independent clients, persistence after reconnecting,
stale-save rejection, incorrect access codes, invalid messages, and origin checks.
Test the two-tab demo on the live deployment before presenting it.

## Primary references

- https://channels.readthedocs.io/en/stable/installation.html
- https://channels.readthedocs.io/en/stable/topics/channel_layers.html
- https://render.com/docs/websocket
