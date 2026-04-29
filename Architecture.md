# Architecture

## Overview

InteractiveGen is a pipeline of four loosely coupled stages: Stream, Prompt, Generate, Transition. Each stage is independently replaceable as the underlying video generation ecosystem matures.

```mermaid
graph TD
    Client["Client\n(Video Player + Prompt Input)"]
    SM["Session Manager\n- Current segment reference\n- Scene context window\n- Prompt queue\n- Playback state machine"]
    GE["Generation Engine"]
    GT["1. Generate target segment"]
    GTR["2. Generate transition segment"]
    EM["3. Emit segments to client"]

    Client -->|"text / voice prompt"| SM
    SM -->|"segment stream"| Client
    SM --> GE
    GE --> GT
    GT --> GTR
    GTR --> EM
    EM -->|"transition + new loop segment"| SM
```

## Playback State Machine

```mermaid
stateDiagram-v2
    [*] --> IDLE_LOOP

    IDLE_LOOP --> GENERATING_TARGET : prompt received
    GENERATING_TARGET --> GENERATING_TRANSITION : target segment ready
    GENERATING_TRANSITION --> PLAYING_TRANSITION : transition segment ready
    PLAYING_TRANSITION --> IDLE_LOOP : transition complete\n(new segment now looping)

    note right of GENERATING_TARGET
        Current segment continues\nlooping. No freeze or\nblack frame visible.
    end note

    note right of GENERATING_TRANSITION
        Conditioned on last frame\nof current + first frame\nof target.
    end note
```

## Generation Pipeline

### Step 1 -- Generate Target Segment

On prompt receipt:

1. Enrich the prompt with scene context (current setting, characters, lighting, established continuity)
2. Submit to video generation backend
3. Store resulting segment as `target`

The context window is maintained server-side as a rolling text description of the scene, updated after each accepted prompt. This is passed as conditioning text to the generator to maintain continuity of characters, environment, and tone.

### Step 2 -- Generate Transition

Once `target` is ready:

1. Extract last frame of current looping segment as `frame_A`
2. Extract first frame of `target` as `frame_B`
3. Submit to video generation backend: "generate a smooth visual transition from frame_A to frame_B, maintaining consistent style"
4. Store resulting segment as `transition`

Transition duration implicitly encodes scene distance. A prompt moving within the same room produces a short transition. A prompt crossing settings or time produces a longer one. This is a feature -- it gives the user feedback that a large change is incoming.

### Step 3 -- Emit

1. Signal client to queue transition after current loop boundary
2. Follow transition with target segment in continuous loop
3. Update scene context window with description of new scene

## Component Architecture

```mermaid
graph LR
    subgraph Client
        VP["Video Player"]
        PI["Prompt Input\n(text / voice)"]
    end

    subgraph Server
        API["FastAPI\nSession Manager"]
        Redis["Redis\nSession State"]
        GE["Generation Engine\n(async)"]
        GL["Guardrail Layer\nPrompt Classifier"]
    end

    subgraph Backends
        Kling["Kling"]
        Runway["Runway Gen-3"]
        Sora["Sora (planned)"]
        Local["Local\nComfyUI + SVD"]
    end

    VP -->|"segment stream"| API
    PI -->|"prompt"| API
    API --> Redis
    API --> GL
    GL -->|"approved prompt + context"| GE
    GE --> Kling
    GE --> Runway
    GE --> Sora
    GE --> Local
```

## Video Backends

| Backend | Status | Notes |
|---|---|---|
| Kling | Supported | Good temporal consistency, API available |
| Runway Gen-3 | Supported | Strong transition quality |
| Sora | Planned | API access limited at time of writing |
| Local (ComfyUI + SVD) | Experimental | High latency, no API cost |

Backend selection is per-deployment via `config.yaml`. Multiple backends can be configured with fallback ordering.

## Sequence -- Full Prompt Cycle

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant SessionManager
    participant GuardrailLayer
    participant GenerationEngine
    participant VideoBackend

    User->>Client: enters prompt
    Client->>SessionManager: POST /prompt
    SessionManager->>GuardrailLayer: classify(prompt)
    GuardrailLayer-->>SessionManager: approved / rejected

    alt approved
        SessionManager->>GenerationEngine: generate_target(prompt, context)
        GenerationEngine->>VideoBackend: submit job
        VideoBackend-->>GenerationEngine: target segment
        GenerationEngine->>VideoBackend: generate_transition(frame_A, frame_B)
        VideoBackend-->>GenerationEngine: transition segment
        GenerationEngine-->>SessionManager: transition + target ready
        SessionManager->>Client: stream transition then target
        Client->>User: plays transition, then loops target
    else rejected
        SessionManager-->>Client: prompt rejected (policy)
        Client->>User: display rejection reason
    end
```

## Guardrail Layer

- Prompt classification before submission to generator
- Category enforcement configurable per deployment profile
- Age verification gate at session initialisation where required
- Implemented as a lightweight classifier (local model preferred for latency)

## Configuration

All deployment behaviour is controlled via `config.yaml`:

```yaml
backend:
  primary: kling
  fallback: [runway, local]

guardrails:
  profile: default          # default | adult | art_installation
  age_gate: false

session:
  context_window_tokens: 2048
  max_queued_prompts: 5

generation:
  target_duration_seconds: 6
  transition_max_duration_seconds: 4
```
