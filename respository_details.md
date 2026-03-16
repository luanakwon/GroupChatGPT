# Repository Details

## Structure
```text
GroupChatGPT/
├── images/                    # Documentation assets
├── bots/                      # Source Code Root
│   ├── main.py                # Entry point; initializes Discord & LLM clients
│   ├── configs/             
│   │   ├── credentials.py     # API key loading & secret management
│   │   └── mylogger.py        # Global logging configuration
│   ├── discord/
│   │   ├── discord_client.py  # Main event loop (on_message, history fetching)
│   │   └── simple_message.py  # Data Class: Standardizes Discord data for LLM
│   └── llm/
│       ├── llm_client.py      # OpenAI wrapper; handles Mode 1 & Mode 2 logic
│       └── prompt.py          # System instructions & persona definitions
├── README.md                  # Project overview & setup
└── privacy.md                 # Privacy policy/data handling details
```

## Flowchart
```mermaid
graph TD
    subgraph Phase 1: Initialization
        A([Start: main.py]) --> B[Load Configs: credentials, mylogger]
        B --> C[Instantiate: llm_client & discord_client]
        C --> D([Connect to Discord])
    end

    D --> E([Event: on_message])

    subgraph Phase 2: Event Loop & Pre-processing
        E --> F{Is Author Bot?}
        F -->|Yes| Z1([Ignore Message])
        F -->|No| G{Bot Triggered?}
        G -->|No| Z2([Ignore Message])
        G -->|Yes| H[Privacy Filter: omit_hidden_message]
        H --> I{Is Result Empty? <br> e.g. started with //pss}
        I -->|Yes| Z3([Ignore Message])
        I -->|No| J[Clean Data: convert_nontext2str <br> replace_mention_id2name]
        J --> K[Standardize: simple_message]
    end

    subgraph Phase 3: Immediate Context Mode 1
        K --> L[Fetch Recent History: fetch_recent_messages]
        L --> M[Sanitize History: Apply Privacy Filter & Cleaners]
        M --> N[First Invoke: llm_client.invoke <br> Query + Recent Context]
        N --> O{LLM Decision: <br> Enough Context?}
    end

    subgraph Phase 4: Deep Retrieval Mode 2
        O -->|No: Needs Context| P[Extract Search Keywords]
        P --> Q[Search History: fetch_messages_matching_keywords]
        Q --> R[Sanitize Retrieved Data: Apply Privacy Filter]
        R --> S[Second Invoke: llm_client.invoke <br> Query + Recent + Retrieved Context]
    end

    subgraph Phase 5: Delivery
        O -->|Yes: Sufficient| T[Generate Final Response]
        S --> T
        T --> U[Send Response to Discord Channel]
        U --> V([Wait for Next Event])
    end

    %% Looping back to the event listener
    V -.-> E
    
    %% Styling to make decisions stand out
    classDef decision fill:#f9f,stroke:#333,stroke-width:2px,color:#000;
    class F,G,I,O decision;
```


### Example Context for Coding Agent

If you are pasting this into a new chat or a system prompt to "prime" an AI, you can use this concise block:

> "This repo is a Python Discord bot. `main.py` starts the service. `discord_client.py` handles events and uses `omit_hidden_message` to ignore `//pss` prefixes. Context is gathered via `fetch_recent_messages` or keyword-based retrieval. All LLM calls go through `llm_client.py:invoke()`, which abstracts the OpenAI API. Configs and logs are handled in the `bots/configs/` directory."
