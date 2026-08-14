# 🧬 SoulAdapt

<div align="center">

**An adaptation & sincerity layer for AI companions.**
Companion to [SoulMemory](https://github.com/Romazea/soulmemory).

</div>

<div align="center">

[![PyPI version](https://img.shields.io/pypi/v/souladapt.svg)](https://pypi.org/project/souladapt/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 🎯 Why SoulAdapt?

Most AI companions either **invent memories** or treat every user exactly the same. SoulAdapt fixes both:

- 🎛️ **Adapts** how the AI talks: style, sensitive topics, interests
- 💎 **Never invents**: calibrates honesty to the real memory signal
- 🪶 **Zero dependencies**: pure Python standard library
- 🤝 **Compatible, not dependent**: works with SoulMemory or _any_ object with `.recall()`

## ✨ Features

| Feature                | Description                                           |
| ---------------------- | ----------------------------------------------------- |
| `observe()`            | Learn something about the user                        |
| `observations()`       | What the companion learned, strongest first           |
| `forget_observation()` | Unlearn something                                     |
| `decide()`             | How to respond: style, avoid-list, interests, honesty |
| `SincerityEngine`      | distance → confidence → assertive / hedged / admit    |

## 📦 Installation

```bash
pip install souladapt
```

## 🚀 Quick Start

### Standalone (no memory connected)

```python
from souladapt import SoulAdapt

adapt = SoulAdapt("adapt.db")

adapt.observe("Prefiere respuestas cortas", category="style")
adapt.observe("Ruptura con Ana", category="sensitive")

d = adapt.decide("hola")
# → {'style': ['Prefiere respuestas cortas'],
#    'avoid': ['Ruptura con Ana'], 'interests': [],
#    'memories': [], 'confidence': None, 'honesty': 'neutral'}
```

### Connected to SoulMemory

```python
from soulmemory import SoulMemory   # optional extra: pip install souladapt[soulmemory]
from souladapt import SoulAdapt

mem = SoulMemory("memory.db")
adapt = SoulAdapt("adapt.db", memory=mem)

d = adapt.decide("¿qué sabes de Ana?")
# → honesty calibrated from real recall distances
```

## 💎 The three honesty levels

```
confidence ≥ 0.75 → assertive   "You had coffee with Ana."
0.45 – 0.75       → hedged      "If I remember correctly: ..."
< 0.45            → admit       "I don't have a clear memory..."
```

The AI never invents: if the memory is weak, it admits it.

## 🤝 The contract (duck typing)

SoulAdapt **never imports SoulMemory**. Any object satisfies the contract if it has:

```
.recall(query, limit)  → list of dicts with "content" and "distance"
```

SoulMemory satisfies it out of the box. So does your own memory system.

## ️ Observation categories

```
style     → how to talk to the user ("short answers", "casual tone")
sensitive → topics to handle with care ("breakup with Ana")
interests → what they like ("cats", "gym")
general   → everything else
```

## 📚 API Reference

### `SoulAdapt(db_path="souladapt.db", memory=None)`

Create an adapter. `memory` is any SoulMemory-like object (optional).

### `observe(content, category="general")`

Register something learned about the user. Repeated observations get reinforced, not duplicated.

### `observations(category=None)`

Get learned observations, strongest first.

### `forget_observation(observation_id)`

Delete an observation: the companion unlearns it.

### `decide(query, limit=3)`

Decide HOW the AI should respond. Returns style hints, topics to avoid, interests, evaluated memories, confidence and honesty level.

### `close()`

Close the database connection.

## 🎬 Examples

```bash
python examples/demo_adapt.py   # standalone + connected to SoulMemory
```

## 🗺️ Roadmap

- [x] Observations (reinforcement learning-lite)
- [x] `decide()` adaptation layer
- [x] `SincerityEngine` (3 honesty levels)
- [ ] Habit & routine detection
- [ ] Tone presets (formal / casual / warm)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [SoulMemory](https://github.com/Romazea/soulmemory) — the memory layer this adapts to

---

<div align="center">

**Made with ❤️ as part of the Soul ecosystem**

</div>
