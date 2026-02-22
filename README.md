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
├── mcp/                        # 🔌 Tool-Calling Layer
│   ├── __init__.py
│   ├── tool_registry.py        # Tool definitions
│   └── tool_executor.py        # Executes tool calls
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
    └── helpers.py

