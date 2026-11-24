# Architecture

## Components

```mermaid
flowchart LR
    U[User]
    UA[User agent<br/><b>user_agent.py</b>]

    subgraph Shops["Shop onboarding"]
        SK[Shopkeeper]
        ON[Onboarding<br/><b>onboard.py</b>]
        OC[Owner console<br/><b>owner.py</b>]
    end

    subgraph Host["Browser Proxy Twin host - server.py"]
        HTTP[Threading HTTP server<br/>JSON routes + rate limiting]
        HUB[Hub]
        DIR[(Directory<br/><b>directory.py</b>)]
        SA1[Shop agent: salon]
        SA2[Shop agent: clinic]
        SAN[Shop agent: ...]
        HOLD[(In-memory holds and bookings<br/>inside each shop agent)]
        PERSIST[(Optional JSON<br/>card persistence)]
    end

    U -->|Natural-language request| UA
    UA -->|GET /cards<br/>category, area, language| HTTP
    HTTP --> HUB
    HUB --> DIR
    DIR -.->|loaded cards| PERSIST
    SK -->|description in text| ON
    ON -->|validated agent card| OC
    OC -->|owner confirms card| ON
    ON -->|POST /cards| HTTP
    HTTP -->|register card| HUB
    HUB -->|create hosted agent| SA1
    HUB -->|create hosted agent| SA2
    HUB -->|create hosted agent| SAN

    UA -->|POST /agents/SHOP_ID/message<br/>query, hold, status, book, cancel| HTTP
    HTTP --> HUB
    HUB --> SA1
    HUB --> SA2
    HUB --> SAN
    SA1 <--> HOLD
    SA2 <--> HOLD
    SAN <--> HOLD

    OC -->|GET pending / POST decision| HTTP
    HTTP -->|owner inbox routes| SA1

    UA -->|Ask for final approval| U

    classDef actor fill:#FFF7E6,stroke:#A15C00,color:#000;
    classDef client fill:#E8F4FF,stroke:#1F5FA7,color:#000;
    classDef host fill:#F3F0FF,stroke:#6750A4,color:#000;
    classDef data fill:#EAF7EE,stroke:#217346,color:#000;
    class U,SK,OC actor;
    class UA,ON client;
    class HTTP,HUB,SA1,SA2,SAN host;
    class DIR,HOLD,PERSIST data;
```

| Component | File | Responsibility |
|---|---|---|
| Agent card | `schema.py` | Validate a card and generate its slots for a date |
| Directory | `directory.py` | Store cards, search by category, area, language |
| Shop agent | `shop_agent.py` | Answer from the card, lock slots, manage holds, never double-book |
| Server | `server.py` | HTTP routes, one hosted shop agent per card, rate limiting |
| User agent | `user_agent.py` | Parse the request, discover, compare, negotiate, book |
| Onboarding | `onboard.py` | Turn a description into a card; the owner confirms before publishing |
| Owner console | `owner.py` | Stand-in for the WhatsApp confirmation |

## One booking, step by step

```mermaid
sequenceDiagram
    participant U as User
    participant UA as User agent
    participant D as Directory
    participant S as Shop agent
    participant O as Owner (WhatsApp)
    U->>UA: "Book a haircut tomorrow evening"
    UA->>D: GET /cards?category=salon
    D-->>UA: cards
    UA->>S: query (date)
    S-->>UA: offer (price, free slots)
    UA->>S: hold (slot)
    S-->>UA: hold_result: pending_owner (slot locked)
    S->>O: Confirm this request?
    O-->>S: Confirm
    UA->>S: status
    S-->>UA: held
    UA->>U: Approve this booking?
    U-->>UA: Approve
    UA->>S: book
    S-->>UA: booked (BK-...)
```

If the owner declines, the hold is released and the user agent moves to the next-best shop.

## Design decisions

- **Hold before asking the owner.** The slot is locked the moment a hold is created. Two agents racing for the same slot cannot both win (see `test_concurrent_holds_never_double_book`).
- **Holds expire.** An owner who never answers cannot block a slot forever; the user agent times out and tries the next shop.
- **The owner channel is separate from the protocol.** Swapping the console for WhatsApp, SMS or a voice call changes one adapter, not the agents.
- **Standard library only.** Anyone can run it with Python 3.10+ and no install step.
- **Rule-based onboarding for now.** It keeps the prototype dependency-free and testable. The LLM version replaces `parse_description` and keeps the same output (a validated card).
- **Minimum data shared.** Agents exchange an opaque `customer_ref`, not names or phone numbers.

## Scaling path

- Directory to a database with geo and category indexes; shop agents to stateless workers with holds in the database.
- Federated directories so regional registries can interoperate.
- Channel adapters (WhatsApp Business API, SMS, IVR) behind the owner interface.
