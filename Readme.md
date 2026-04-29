# ![PyVidSteer](resources/icon.png) InteractiveGen

> Natural language steering of generative video streams in real time.

## Concept

InteractiveGen is a platform for interactive, prompt-steered generative video. A default video loop plays continuously. The viewer types or speaks a prompt -- "she walks to the window", "cut to the street below", "it starts raining" -- and the video transitions to a new generated segment matching the instruction, then loops that segment until the next prompt arrives.

Without input, the video folds back on itself. With input, it goes somewhere new.

## Core UX

- Video plays in a continuous loop at idle
- User enters a natural language prompt at any time
- A transition segment is generated bridging current scene to new scene
- New scene plays and loops
- Latency is expected and contextual -- a scene change within a room is fast; a jump from city apartment to spaceship takes longer and that is acceptable

## Use Cases

- Interactive narrative and storytelling
- Generative cinema / art installations
- Game cinematics driven by player input
- Training data generation for video models
- Adult content (age-gated, guardrailed -- see [CONTENT_POLICY.md](CONTENT_POLICY.md))

## Status

Concept / pre-prototype. Architecture documented in [Architecture.md](Architecture.md).

## Requirements

- Python 3.11+
- A supported video generation backend (see Architecture)
- GPU with minimum 16GB VRAM recommended for local inference
- Redis or equivalent for session/state management

## Quickstart

```bash
git clone https://github.com/yourorg/interactivegen
cd interactivegen
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml -- set your backend, API keys, guardrail policy
python -m interactivegen.server
```

Then open `http://localhost:8080` in a browser.

## License

MIT
