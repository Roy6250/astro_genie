astro-intelligence-platform/
│
├── main.py                     # FastAPI app entry
├── config.py                   # Environment configs
├── requirements.txt
├── README.md
│
├── api/                        # Interface Layer
│   ├── __init__.py
│   └── webhook.py              # WhatsApp webhook endpoint
│
├── core/                       # System Core Logic
│   ├── __init__.py
│   ├── orchestrator.py         # Main Agent Orchestrator
│   ├── state_machine.py        # FSM logic
│   └── event_router.py         # Routes events to agents
│
├── workers/                    # Async Execution Layer
│   ├── __init__.py
│   └── celery_worker.py
│
├── memory/                     # 🧠 Memory Layer
│   ├── __init__.py
│   ├── mongo_manager.py        # Structured memory
│   ├── vector_store.py         # Semantic memory
│   └── insight_extractor.py    # Stores emotional traits
│
├── agents/                     # 🤖 Specialized Agents
│   ├── __init__.py
│   ├── astrology_agent.py
│   ├── numerology_agent.py
│   ├── interpretation_agent.py
│   ├── formatter_agent.py
│   ├── safety_agent.py         # Guards risky outputs
│   └── escalation_agent.py     # Human handoff
│
├── mcp_serv/                   # 🔌 MCP server (SSE) + client for tool calls
│   ├── server.py               # Run: python -m mcp_serv.server (port 8001)
│   └── client.py               # call_tool(url, name, arguments)
├── integrations/               # External APIs (Prokerala, etc.)
│   └── prokerala/              # Daily horoscope (auth, daily_horoscope, formatter)
│
├── services/                   # External Integrations
│   ├── __init__.py
│   ├── whatsapp_service.py
│   ├── llm_service.py
│   ├── astrology_api_service.py
│   └── embedding_service.py
│
├── models/                     # DB Schemas
│   ├── __init__.py
│   ├── user_profile.py
│   ├── state_model.py
│   ├── chat_model.py
│   ├── astro_model.py
│   ├── numero_model.py
│   └── insight_model.py
│
├── prompts/                    # Versioned Prompts
│   ├── system.txt
│   ├── basic_reading.txt
│   ├── followup.txt
│   └── safety_rules.txt
│
├── observability/              # Monitoring & Evaluation
│   ├── __init__.py
│   ├── tracing.py              # LangSmith / Phoenix hooks
│   └── evaluator.py            # LLM-as-judge scoring
│
└── utils/
    ├── logger.py
    ├── helpers.py
    └── zodiac.py               # dob_to_sun_sign() for daily horoscope

---

### Daily horoscope (MCP + Prokerala)

- **Run order**: Start the MCP server, then the FastAPI app.
  1. From `astro_genie`: `python -m mcp_serv.server` (listens on `http://localhost:8001/sse` by default).
  2. Start the app (e.g. `uvicorn main:app`).
- **Env**: `PROKERALA_CLIENT_ID`, `PROKERALA_CLIENT_SECRET` for the horoscope API; `MCP_SERVER_URL` (default `http://localhost:8001/sse`) for the orchestrator.

### Kundli tool (MCP + Prokerala)

- MCP tool name: `get_kundli`
- Required args:
  - `date_of_birth` (`YYYY-MM-DD`)
  - `place` (city/place name)
- Optional args:
  - `time_of_birth` (`HH:MM`, default `12:00`)
  - `latitude`, `longitude` (if you already have coordinates)
  - `timezone` (IANA zone, e.g. `Asia/Kolkata`)
  - `ayanamsa` (`1`/`3`/`5` or `lahiri`/`raman`/`kp`)
  - `la` (`en`/`hi`/`ta`/`ml`) or `language` alias
  - `year_length` (`1` for 365.25 days, `0` for 360 days)
  - `include_dasha_periods` (default `true`)
  - `include_mangal_dosha` (default `true`)
- Location handling:
  - If coordinates are not provided, the tool resolves `place` using free Open-Meteo geocoding.
- Response includes:
  - `kundli`
  - `dasha_periods` (when enabled)
  - `mangal_dosha` (when enabled)

### WhatsApp webhook (Wasender)

- Set webhook URL in Wasender session settings to `https://<your-domain>/webhook`.
- Subscribe to message events (recommended: `messages.received`; optionally `messages.upsert`).
- Optional security: set `WASENDER_WEBHOOK_SECRET` in `.env`; incoming `X-Webhook-Signature` must match.
- Local endpoints:
  - `POST /webhook` for Wasender callbacks
  - `GET /webhook` health check
  - `POST /simulate-message` for manual local testing

