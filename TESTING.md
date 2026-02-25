# Testing the MCP + Prokerala daily horoscope flow

## 1. Prerequisites

- **MongoDB** running (e.g. `mongodb://localhost:27017`).
- **.env** in `astro_genie/` with at least:
  - `PROKERALA_CLIENT_ID` and `PROKERALA_CLIENT_SECRET` (from [Prokerala](https://api.prokerala.com/article/how-to-get-client-id-and-client-secret-for-api-requests.html)).
  - Optional: `MCP_SERVER_URL=http://localhost:8001/sse` (default).

Install deps (from repo root or astro_genie):

```bash
pip install -r requirements.txt
```

---

## 2. Test pieces in isolation (no servers)

From the **astro_genie** directory (so imports work):

```bash
cd astro_genie
```

**Intent classifier**

```bash
python -c "
from agents.intent_agent import classify
print(classify('What is my daily prediction?'))   # expect ('daily_prediction', {})
print(classify('Tell me about my career'))        # expect ('general_question', {})
"
```

**DOB → zodiac sign**

```bash
python -c "
from utils.zodiac import dob_to_sun_sign
print(dob_to_sun_sign('15-03-1995'))   # pisces
print(dob_to_sun_sign('25-04-1990'))   # taurus
"
```

**Prokerala client (needs real credentials in .env)**

```bash
python -c "
from integrations.prokerala.daily_horoscope import get_daily_horoscope
from integrations.prokerala.formatter import format_daily_horoscope_response
r = get_daily_horoscope('virgo')
print(format_daily_horoscope_response(r))
"
```

---

## 3. Test the MCP server

**Terminal 1 – start MCP server**

```bash
cd astro_genie
python -m mcp_serv.server
```

Default: http://127.0.0.1:8001, SSE at http://127.0.0.1:8001/sse.

**Terminal 2 – call the tool via client**

```bash
cd astro_genie
python -c "
import asyncio
from mcp_serv.client import call_tool
async def run():
    out = await call_tool('http://127.0.0.1:8001/sse', 'get_daily_horoscope', {'sign': 'virgo'})
    print(out)
asyncio.run(run())
"
```

You should see a formatted daily horoscope (or an error if Prokerala creds are missing/invalid).

---

## 4. Test the full app flow (orchestrator → MCP → reply)

The daily-horoscope path runs only when:

- The user **has a persona** (numerology stored in `astro_data`), and  
- The message is classified as **daily_prediction**.

**4.1 Ensure a test user in MongoDB**

Either use an existing user who already completed the numerology flow, or insert a minimal test user:

```javascript
// In mongosh or Compass, database astro_genie:

// 1) Profile with DOB (users collection)
db.users.updateOne(
  { "phone": "1234567890" },
  { "$set": { "phone": "1234567890", "dob": "15-03-1995", "updated_at": new Date() } },
  { upsert: true }
);

// 2) Persona with numerology (astro_data collection) so orchestrator uses “follow-up” path
db.astro_data.updateOne(
  { "phone": "1234567890" },
  { "$set": { "phone": "1234567890", "data": { "numerology": { "life_path_number": 5 } }, "updated_at": new Date() } },
  { upsert: true }
);
```

**4.2 Start both processes**

- **Terminal 1:** `cd astro_genie && python -m mcp_serv.server`
- **Terminal 2:** `cd astro_genie && uvicorn main:app --reload`

**4.3 Send a daily-prediction message**

```bash
curl -X POST http://localhost:8000/simulate-message \
  -H "Content-Type: application/json" \
  -d '{"phone": "1234567890", "message": "What is my daily prediction?"}'
```

Use the same `phone` as in MongoDB. The app will:

1. Classify intent → `daily_prediction`
2. Get sign from profile DOB (e.g. pisces)
3. Call MCP `get_daily_horoscope` with that sign
4. Send the formatted reply via `send_whatsapp_message(phone, reply)` (check console/logs for the reply if WhatsApp isn’t wired).

---

## 5. Run the automated test script (optional)

From **astro_genie**:

```bash
cd astro_genie
python scripts/test_daily_horoscope.py
```

This script runs intent + zodiac + (if MCP server is up) one MCP tool call. See script for what it prints.
