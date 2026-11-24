# Services, servers and self-hosted apps

The reader is an **operator**: can I run it here, what does it need, how do
I reach it, and how do I keep my data safe across upgrades?

## Decision card

- Deployment routes that exist: compose file, container image, package,
  binary, a platform template.
- What it needs alongside: database, cache, queue, object storage, a
  reverse proxy, a domain and TLS.
- Ports, the URL to open first, the first account or token.
- Configuration and secrets: every required environment variable, with a
  safe example value; defaults.
- Persistent state: volumes and paths; backup, restore, upgrade.
- Resource needs if stated; network calls it makes on its own.
- For a cloud deployment: the account and the setup steps in the order
  they must run; what it costs to leave running (from the resources it
  creates: always-on servers, managed databases, load balancers), and how
  to tear it down, including anything that survives deletion.

## Where to look

- `Dockerfile`, `compose.yaml` (`ports`, `volumes`, `environment`,
  `depends_on`), Helm charts, systemd units.
- Routes and handlers (Express, FastAPI, Flask, Django URLs, Gin, Axum,
  Rails routes); OpenAPI files.
- Configuration loading and environment variables read; `.env.example`.
- Migrations and seed data; health and readiness endpoints.
- Admin and maintenance commands (create user, backup, migrate).

## Show it working

The start command and the first request that works, with its real
response; or, for a web interface, a screenshot of the first screen after
setup made from seeded sample data (see [pictures](pictures.md#web-apps)).
Run it in a throwaway container or folder with sample data; never show a
real instance's data.

## Page

1. Name and pitch
2. Link row
3. A picture of the interface, or the first request and response
4. Features (4 to 7)
5. Install: the lead route (often compose), then "open http://localhost:PORT
   and …", the required settings as a short table, update and remove
6. First use: the first account, the first object, the first API call
7. Configuration: the environment variables that matter, the rest in the guide
8. Your data: volumes, backup, what leaves the server
9. More

Targets: 500 to 900 words.

## Pitfalls

- Secrets with real-looking values in examples (the checker flags known
  token shapes; use `change-me`).
- Ports and paths that differ from the compose file.
- "Production-ready" with no word on backup or upgrade.
- An architecture diagram where the deployment steps should be.
