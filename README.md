# Browser Proxy Twin

> **We're not building an agent that uses the web. We're building the web that agents can use, for everyone.**

Instead of your AI agent clicking through a company's human-designed website, it negotiates directly with the business's **own agent** through a tiny open protocol. A kirana store, clinic, salon or ward office publishes a simple **agent card** (services, prices, hours, required documents). No website is needed, and no browser is needed on either side. The user gets a booking in seconds without a single page loading.

| | |
|---|---|
| **Team** | COMMAND CATALYST (Team ID `4ee6d85c`) |
| **Event** | wHACKiest 2026 online ideathon, Ramaiah Institute of Technology, 26-27 Nov 2026 |
| **Track** | Beyond the Browser *(edit if your registered track differs)* |
| **Demo video** | `https://www.youtube.com/watch?v=5ys9sIMIq_Q` |
| **Pitch deck** | `\docs\wHACKiest26.pptx` |

---

## The problem

- AI agents are being taught to click through websites. That is slow and brittle (a UI change breaks them), and it is blocked by logins and CAPTCHAs.
- India has an estimated 60 million+ small businesses; most have **no website** and run on phone calls, WhatsApp and UPI. To an agent, they are invisible.
- The agentic web is being built only for businesses that already have good websites, which widens the digital divide.

## The solution

A hosted **agent card** layer that makes any business reachable by agents:

1. **Zero-tech onboarding.** The shopkeeper describes the business once, in their own language (Tamil and English in this prototype). The system produces a validated agent card, and the owner confirms it before it goes live.
2. **Hosted shop agent.** It answers price and slot questions *only from the card*, locks slots, and never double-books. Booking needs the **owner's confirmation** (WhatsApp in production, a console or HTTP stand-in here).
3. **Open protocol.** Five small JSON messages (see [PROTOCOL.md](PROTOCOL.md)) and a directory searchable by category and area.
4. **User agent.** Understands "Book a haircut tomorrow evening", discovers cards, compares shops, falls back to the next shop if an owner declines, and asks the **user to approve** before booking.


More detail: [docs/architecture_README.md](docs/architecture.md) · How this differs from A2A, MCP and ONDC: [docs/comparison.md](docs/comparison.md)

---

## Quick start

Requires **Python 3.10+**. There are **no third-party dependencies**.

```bash
git clone https://github.com/mitracodes2726/COMMAND_CATALYST.git
cd browser-proxy-twin

./run_demo.sh            # or: python3 -m proxytwin.demo
python3 -m unittest discover -s tests -t .     # run the tests (23)
```

On Windows without bash, use `python -m proxytwin.demo`.

### Sample output

```text
== 1. Shops publish agent cards (no website needed) ==
  published Sri Lakshmi Clinic (sample) (clinic)  id=sri-lakshmi-clinic-sample-3b9e61
  published Ganesh Kirana Store (sample) (kirana)  id=ganesh-kirana-store-sample-3742d2
  published Priya Ladies Salon (sample) (salon)  id=priya-ladies-salon-sample-876f70
  published Ward Office, Ward 12 (sample) (office)  id=ward-office-ward-12-sample-def454

== 2. A shopkeeper describes a shop in Tamil + English ==
  நான் சலூன் நடத்துகிறேன், called Meena Beauty Parlour in Saibaba Colony. Haircut ₹150, facial ₹400. Open 10 am to 8 pm. Closed on Sunday. Languages: Tamil and English.
  -> card: Meena Beauty Parlour | salon | Saibaba Colony | [('Haircut', 150), ('Facial', 400)] | 10:00-20:00 | closed ['Sunday']
  owner confirms the card, published with id=meena-beauty-parlour-08f9d5

== 3. The user asks their agent (2026-11-25) ==
  [user agent] understood: salon, 2026-11-25, evening
  [directory] 2 salon card(s) found
  [shop: Priya Ladies Salon (sample)] Haircut Rs 200, free 16:00
  [shop: Meena Beauty Parlour] Haircut Rs 150, free 16:00
  [user agent] best match: Meena Beauty Parlour
  [shop: Meena Beauty Parlour] holding the slot, asking the owner to confirm
  [WhatsApp to Meena Beauty Parlour] request for 16:00 -> DECLINE
  [owner] Meena Beauty Parlour: declined, trying the next shop
  [shop: Priya Ladies Salon (sample)] holding the slot, asking the owner to confirm
  [WhatsApp to Priya Ladies Salon (sample)] request for 16:00 -> CONFIRM
  [owner] Priya Ladies Salon (sample): confirmed 16:00
  [user agent] BOOKED BK-19D3047A: Priya Ladies Salon (sample), 2026-11-25 16:00, Rs 200

== Result: BOOKED | agent messages: 24 | pages loaded: 0 ==
```

Demo options: `--owner accept|decline|decline-first`, `--interactive` (you approve the booking), `--date YYYY-MM-DD`.

### Run the pieces yourself (three terminals)

```bash
# Terminal 1: directory + hosted shop agents
python3 -m proxytwin.server --port 8080

# Terminal 2: onboard a shop (the owner confirms the generated card), then act as its owner
python3 -m proxytwin.onboard --server http://127.0.0.1:8080 --city Coimbatore \
  --text "Tailor shop called Meena Boutique in Saibaba Colony. Blouse stitching ₹280. Open 10 am to 6 pm."
python3 -m proxytwin.owner --shop <id-printed-above>

# Terminal 3: the user's agent
python3 -m proxytwin.user_agent "Book a tailor tomorrow morning"
```

Add `--dry-run` to `onboard` to only print the card. Cards in [`examples/`](examples/) can be posted to `/cards` with any HTTP client.

### Docker

```bash
docker build -t browser-proxy-twin .
docker run -p 8080:8080 browser-proxy-twin
```

Configuration is in [`.env.example`](.env.example) (host, port, hold time-to-live, rate limit, optional JSON persistence file).

---

## Repository layout

```
proxytwin/
  schema.py       agent card validation and slot generation
  directory.py    discovery by category / area / language
  shop_agent.py   the shop's agent: query, hold, status, book, cancel (thread-safe)
  server.py       HTTP server: directory + hosted agents + owner inbox + rate limit
  user_agent.py   the user's agent: parse request, discover, negotiate, book
  onboard.py      shopkeeper onboarding script (stand-in for WhatsApp onboarding)
  owner.py        owner console (stand-in for the WhatsApp confirmation)
  demo.py         one-command end-to-end demo
examples/         sample cards: kirana, clinic, salon, ward office
docs/             architecture, comparison with A2A / MCP / ONDC, assets
tests/            23 tests (schema, slot locking, onboarding, end to end)
PROTOCOL.md       the open agent card spec, five messages, error codes
```

## What is real and what is simulated

Honest status of this prototype:

| Part | Status |
|---|---|
| Agent card spec, validation, slot generation | Real |
| Shop agent: slot locking, holds with expiry, no double booking | Real (tested under 40 concurrent requests) |
| Directory and HTTP protocol | Real, in memory (optional JSON file for cards) |
| User agent: discovery, ranking, owner fallback, user approval | Real, rule-based |
| Onboarding from text | **Rule-based parser**, not an LLM. Handles simple English and Tamil+English descriptions |
| Voice input | Not implemented (text only) |
| WhatsApp | **Simulated** by `owner.py` and the demo's owner simulator |
| Shops in `examples/` and the demo | **Invented sample data**, not real businesses |

## Limitations

- Holds live in memory and are lost on restart.
- No authentication or phone verification yet; only per-IP rate limiting and size limits.
- Dates are plain `YYYY-MM-DD` with no time zones; the prototype assumes one local time zone.
- Tamil support is keyword-based, so fully Tamil descriptions (Tamil numerals, Tamil shop names) need the LLM upgrade.
- Single process, single directory; no federation yet.

## Roadmap

1. LLM plus speech-to-text onboarding for Tamil, Hindi and other languages, with the card read back to the owner.
2. WhatsApp Business API for owner confirmation (the `owner` channel is already a separate interface).
3. Phone-number-verified cards, then Udyam or GST linkage where available.
4. Persistent database, plus abuse controls (reporting, reputation).
5. A2A and MCP adapters, so existing agents can reach a shop without custom code.
6. UPI deep links for payment; pay-at-shop remains the default.

## Team

| Name | Role | USN | GitHub |
|---|---|---|---|
| Mitra.S (Lead) | Team Lead | 71812602135 | https://github.com/mitracodes2726 |
| Moulika.C.V | Team Member 1 | 71812602141 | https://github.com/mitracodes2726 |
| Mohamed Navas | Team Member 2 | 71812602139 | https://github.com/mitracodes2726 |
| Mohamed Atif | Team Member 3 | 71812602138 | https://github.com/mitracodes2726 |

## License

MIT, see [LICENSE](LICENSE).
