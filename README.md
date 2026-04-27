# simple-headache-log

A self-hostable headache tracking app. Track migraine episodes, log pain levels, and export your data — all from a single Docker container that runs anywhere.

![Headache Log Screenshot](https://i.imgur.com/placeholder.png)

## Features

- **One-tap start/stop** — log when a headache begins and ends with a single tap
- **Type & pain tracking** — tag episodes with type (Migraine, Tension, Cluster, etc.) and rate pain 1–10
- **Episode journal** — add notes to any entry after the fact
- **Import / Export** — CSV import and export for backup or migration
- **Mobile-first design** — works on phone, tablet, and desktop
- **Self-hosted** — your data stays on your hardware

## Quick Start (Portainer)

### Method 1: Stack deploy

In Portainer, create a new **Stack** and paste this:

```yaml
version: "3.8"
services:
  headache-log:
    image: ghcr.io/iampatticus/simple-headache-log:latest
    container_name: headache-log
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - headache-data:/app/data
    environment:
      - PORT=5000
      - DATA_FILE=/app/data/headache-log.json

volumes:
  headache-data:
```

### Method 2: Single container

In Portainer's **Containers** → **Add container**:

- **Image:** `ghcr.io/iampatticus/simple-headache-log:latest`
- **Port:** `5000` (host) → `5000` (container)
- **Volume:** `headache-data:/app/data`
- **Restart policy:** `Unless stopped`

Then hit **Deploy**.

---

## First Run

Open `http://your-host:5000` in your browser.

- Tap the **red brain** to start tracking a headache
- Tap the **green brain** to stop the current episode
- Tap any log entry to expand it and add notes

## Data Location

Inside the container, data lives at `/app/data/headache-log.json` (persisted via the named volume).

To backup, use:

```bash
docker cp headache-log:/app/data/headache-log.json ./headache-log-backup.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Internal container port |
| `DATA_FILE` | `/app/data/headache-log.json` | Path to the data file |

## Building from source

```bash
git clone https://github.com/IamPatticus/simple-headache-log.git
cd simple-headache-log
docker build -t headache-log .
docker run -d -p 5000:5000 --name headache-log headache-log
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve web UI |
| `GET` | `/health` | Health check |
| `POST` | `/headache-log-add` | Start a new episode |
| `POST` | `/headache-log-end` | End most recent episode |
| `POST` | `/headache-log-edit` | Edit an entry |
| `POST` | `/headache-log-import` | Import CSV |
| `DELETE` | `/headache-log-delete?id=<id>` | Delete an entry |

## Tech Stack

- **Backend:** Python 3 stdlib (`http.server`)
- **Frontend:** Vanilla HTML/CSS/JS, no build step
- **Storage:** JSON file (SQLite-ready upgrade path)
- **Container:** Docker / Podman

## License

CC0 — public domain, do whatever you want with it.