# Shoal

Rehearse a feature with a shoal of synthetic users before real ones see it. Shoal expands the idea behind [MiroFish](https://github.com/666ghj/MiroFish), an open-source swarm simulator, from "what will people say about it" to "what will people do with it": predicted funnel and adoption with ranges, where and why people drop, the fix worth building first, verdicts on your hypotheses, edge cases the spec forgot, a tracking plan, and a way to score the prediction after launch. Since 0.3.0 it can also follow the launch for some weeks with users telling each other what happened to them, which is the part MiroFish is about.

Created 12 Nov 2026 by Claude (Fable 5.2) for Abhishek Soni. Version 0.3.0 (15 Nov 2026); changes in [CHANGELOG.md](CHANGELOG.md).

## Start here

| You want to | Do this |
|---|---|
| Understand the idea | Read [docs/01-concept-and-product-design.md](docs/01-concept-and-product-design.md) |
| See what it produces | Open [examples/one-tap-reorder/runs/sample/report.html](examples/one-tap-reorder/runs/sample/report.html) |
| Use it on a feature, with Claude | In Claude Code, say "run shoal on <spec or idea>" or `/shoal`. The skill does the rest |
| Use it by hand | See "Command line" below |
| Use it in a browser | `bin/shoal serve --root examples`, then open http://127.0.0.1:8787 |

## Install

```bash
git clone https://github.com/abhisheksoni-iitb/shoal.git
cd shoal
bin/shoal run examples/one-tap-reorder/feature.json --quick   # try it
tools/install_skill.sh                                         # optional: install the Claude skill
```

## Command line

```bash
bin/shoal init my-feature                       # writes my-feature/feature.json
bin/shoal lint my-feature/feature.json          # model errors + design gaps
bin/shoal run my-feature/feature.json           # report in my-feature/runs/<time>/report.html
bin/shoal run my-feature/feature.json --quick   # faster while iterating
bin/shoal run my-feature/feature.json --variant <id>   # a variant as the design under test
bin/shoal run my-feature/feature.json --users 40000 --rep-users 20000   # when the outcome is rare (a few percent)
bin/shoal report <run folder>                   # rebuild after adding sessions.json / edge_review.json
bin/shoal edges my-feature/feature.json         # edge-case list only
bin/shoal spread my-feature/feature.json        # word of mouth only: the launch over several weeks, with users talking
bin/shoal calibrate my-feature/feature.json observed.csv   # pin steps to real numbers
bin/shoal score <run folder> observed.csv       # after launch: predicted vs actual
bin/shoal serve --root <folder>                 # local web app
```

Python 3.9 or newer, standard library only. No install, no network, no API key. A full run takes about three seconds.

## What is in this repository

| Path | What |
|---|---|
| `docs/01-concept-and-product-design.md` | The idea in depth: what MiroFish lacks, how Shoal works, skill vs platform, limits, landscape, roadmap |
| `shoal/` | The engine: `model.py` (load, check, variants), `sim.py` (simulation), `analyze.py` (metrics, ranges, hypotheses, levers, calibration, scoring), `spread.py` (word of mouth), `edges.py` (edge cases, combinations), `report.py` (HTML and Markdown), `pipeline.py`, `server.py` (web app), `__main__.py` (command line), `template.json` |
| `skill/shoal/` | The Claude skill: `SKILL.md`, `references/feature-model.md` (model reference and scoring guide), `references/persona-protocol.md` (how to play users and review edge cases) |
| `tools/install_skill.sh` | Copies the skill and engine to `~/.claude/skills/shoal` (add `--all` for other agents' skill folders). Re-run after any change |
| `examples/one-tap-reorder/` | Made-up sample: spec, model, invented real-data CSV and a full sample run. `feature.word-of-mouth.json` is the same model with a `spread` block; its run is in `runs/word-of-mouth/` |
| `examples/jobpilot-daily-apply/`, `examples/jobpilot-onboarding/`, `examples/shadowmux-co-browsing/` | Runs on the specs of two hackathon product concepts, JobPilot and ShadowMux (13 Nov 2026), each with walkthroughs and an edge-case review |
| `tests/test_shoal.py` | 45 tests: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 -m unittest discover -s tests` |
| `bin/shoal` | Launcher |

## Status

Built and tested: flow checks, simulation, ranges, hypotheses, levers, variants, scenarios (the same design under other assumptions), flows with several good endings, counts from a real volume, measured rates per segment, edge cases and combinations, HTML/Markdown/JSON reports, calibration, scoring, word of mouth over several periods, local web app, Claude skill with persona sessions and edge-case review.

Not built: analytics connectors, base-rate library, MCP server, agents that drive a real prototype, headless language-model mode, hosted platform. See the roadmap in the concept document.

Used on three real work features so far (12 and 14 Nov 2026). Their files are kept with those features' own documents, outside this repository; work content does not belong in `examples/`. The first run found one engine fault (the funnel's main reason ignored blocked users). The second was the first to pin today's flow to measured numbers and compare designs against it; it showed that steps scored from the guide flatter a new design next to measured steps, which led to most of version 0.2.0. No prediction has been scored against a real launch yet.

Last full check, 15 Nov 2026: 45 tests pass; every example model lints clean of errors; the same seed gives the same numbers; `score`, `calibrate`, `init`, the web app (including path-traversal and bad-model refusals) and the installed skill all work.

The behaviour weights, and the talk rates behind the word-of-mouth section, are hand-set defaults that have not yet been fitted to real launches. Treat uncalibrated numbers as hypotheses; trust the ranking of problems more than the levels.

## License

MIT. See [LICENSE](LICENSE).
