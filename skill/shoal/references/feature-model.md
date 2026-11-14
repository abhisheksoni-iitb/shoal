# Feature model reference

A feature model is one JSON file. `shoal init <folder>` writes a working starter. A complete example: `examples/one-tap-reorder/feature.json`.

```json
{
  "feature":      { "id", "name", "summary", "session_budget_s", "repeat", "handles" },
  "segments":     [ { "id", "name", "share", "traits", "context", "capabilities", "exposure", "entry" } ],
  "entry_points": [ { "id", "name", "to", "discovery" } ],
  "steps":        [ { "id", "name", "type", "effort", "clarity", "value", "time_s", "error_rate", "on_error",
                      "requires", "fallback", "grants", "sensitive", "optional", "next", "events", "handles",
                      "observed_continue" } ],
  "dimensions":   { "name": ["value", "value"] },
  "hypotheses":   [ { "id", "text", "metric", "op", "value", "segment" } ],
  "variants":     [ { "id", "name", "note", "patch" } ]
}
```

## feature

| Field | Meaning |
|---|---|
| `id`, `name`, `summary` | Identity. `summary` is one sentence: who it is for and what it lets them do. |
| `session_budget_s` | How long a typical user will give this flow in one sitting, in seconds (default 300). Patient users get more, impatient less. |
| `repeat` | Optional. Share of an average successful user who comes back: `{"d1": 0.4, "d7": 0.25, "d30": 0.12}`. Scaled per user by motivation, errors met and friction felt. |
| `handles` | Edge-case keys the spec covers for the whole flow (see "Edge-case keys"). |

## segments

Kinds of user that behave differently. Shares are scaled to add up to 1.

| Field | Meaning |
|---|---|
| `share` | Share of the eligible population. |
| `traits` | `motivation`, `skill`, `patience`, `trust`, each 0 to 1. Segment averages; individuals vary around them (sd 0.13). |
| `context` | Situations and their odds, e.g. `{"device": {"mobile": 0.8, "desktop": 0.2}, "network": {"good": 0.85, "flaky": 0.13, "offline": 0.02}}`. `device` and `network` change behaviour (see below); any other key is used for `when` routing and for the "by situation" table. |
| `capabilities` | What users have, with the odds of having it: `{"saved_card": 0.6, "admin_role": 0.1}`. A plain list means everyone has them. |
| `exposure` | 0 to 1. Share of the segment that is ever in a position to see an entry point (uses the product often enough, is on the right plan). |
| `entry` | Which entry point they would meet: `{"home_banner": 0.7, "email": 0.3}`. Empty = any, equally. |

Trait guide:

| | 0.2 | 0.5 | 0.8 |
|---|---|---|---|
| motivation | Mild curiosity; has a working alternative | Wants it, not urgently | Has the problem now and is looking for this |
| skill | New to the product and the domain | Regular user | Power user; forgives rough edges |
| patience | Gives it seconds; leaves at the first hitch | One retry | Will read, retry and work around |
| trust | First contact; wary of data or money steps | Uses the product, has no reason to worry | Long relationship |

Behaviour built in: `network: flaky|slow` makes `wait` and `external` steps 2.5× slower and 3× more error-prone; `network: offline` makes them fail unless the step lists `offline` in `handles`; `device: mobile` raises input errors by 30%.

## entry_points

| Field | Meaning |
|---|---|
| `to` | First step. |
| `discovery` | Of the users who could meet this entry point, the share who notice it AND choose to start. |

Discovery base rates when there is no data (be conservative; this number dominates adoption):

| Entry point | Typical |
|---|---|
| Banner or card on a busy screen | 0.05 to 0.15 |
| Prominent button on the screen where the need arises | 0.25 to 0.5 |
| Menu item or settings entry | 0.03 to 0.1 |
| Push notification or email | 0.03 to 0.12 |
| Forced step (part of onboarding or checkout) | 0.9 to 1.0 |
| Contextual prompt at the exact moment of need | 0.3 to 0.6 |

## steps

| Field | Meaning |
|---|---|
| `type` | `view` (reads/looks), `input` (types/picks), `decision` (chooses a path), `wait` (waits for something), `external` (another system does work: payment, API, email), `success` (the outcome you want). |
| `effort` | 0 to 1. Work asked of the user at this step. |
| `clarity` | 0 to 1. How obvious it is what to do and what will happen. |
| `value` | 0 to 1. How visible the payoff is at this point. |
| `time_s` | Median seconds for an average user. |
| `error_rate` | Chance the step fails for an average user on a good day. |
| `on_error` | `{"recoverable": true}` lets the user retry (up to 3 times, depending on patience); `{"to": "step_id"}` sends them elsewhere. Leave it out if the spec does not say: lint reports it and the simulation treats the error as a dead stop. |
| `requires` | Capabilities needed. Users without them go to `fallback`, or are **blocked** if there is none. |
| `fallback` | Step for users lacking a requirement. Give that step `grants` so they can return. |
| `grants` | Capabilities gained by completing this step. |
| `sensitive` | `true` for money, personal data, permissions or irreversible actions: low-trust users drop here. |
| `optional` | `true` if the user can skip it (a "skip" instead of an exit). |
| `next` | Where to go: `["step"]`, or weighted and conditional: `[{"to": "a", "weight": 0.3}, {"to": "b", "weight": 0.7, "when": {"device": "mobile"}}]`. `when` can test any context key, `segment`, `has` or `lacks` (capabilities). |
| `events` | Analytics events fired at this step. Missing events are reported as blind spots. |
| `handles` | Edge-case keys the spec explicitly covers at this step. |
| `observed_continue` | A real carry-on rate (0 to 1, exclusive) from analytics. When set, the step reproduces it and ignores effort/clarity/value. |

Scoring guide (score from the least-prepared realistic user's side; when torn, pick the less favourable):

| | 0.1 | 0.3 | 0.5 | 0.7 | 0.9 |
|---|---|---|---|---|---|
| effort | One tap | A choice from a short list | A short form (3 to 5 fields) | A long form, or finding information elsewhere | Leaving the product to fetch something, uploads, approvals from others |
| clarity (inverse of confusion) | Unclear what this is or what happens next | Jargon; several plausible actions | Understandable after reading | One obvious action, plain words | One action, outcome stated, nothing else on screen |
| value | No sign of the payoff yet | Payoff promised in words | Payoff previewed | Partial payoff already received | The payoff itself |

Error-rate base rates: plain form step 0.03 to 0.10; format-sensitive input (dates, IDs, addresses) 0.10 to 0.25; file upload 0.10 to 0.20; payment 0.03 to 0.08; third-party API 0.01 to 0.05; email or SMS code delivery 0.05 to 0.12.

## dimensions

Conditions worth combining, e.g. `{"basket": ["all in stock", "some out of stock"], "card": ["valid", "expired", "none"]}`. Shoal produces the smallest set of combinations in which every pair of values appears together once, as a test list. A dimension whose name matches a segment `context` key also gets a rough "share of users" figure.

## hypotheses

`{"id": "H1", "text": "…", "metric": "completion_rate", "op": ">=", "value": 0.6, "segment": "new_customer"}`

Metrics: `discovery_rate` (started ÷ eligible), `completion_rate` (finished ÷ started), `adoption_rate` (finished ÷ eligible), `error_rate` (met an error ÷ started), `blocked_rate`, `median_time_s`, `repeat_d1` / `repeat_d7` / `repeat_d30`, `step_continue:<step id>`. `segment` is optional. Verdict: supported if it holds in at least 90% of replications, contradicted at 10% or fewer, otherwise uncertain.

## variants

Alternative designs, run against the base on the same synthetic users.

```json
{"id": "inline-card", "name": "Add a card inline", "note": "…",
 "patch": {
   "steps": {"confirm_pay": {"fallback": "add_card"}},
   "add_steps": [{"id": "add_card", "type": "input", "grants": ["saved_card"], "next": ["confirm_pay"]}],
   "remove_steps": ["pick_slot"],
   "segments": {"new_customer": {"exposure": 0.5}},
   "entry_points": {"home_banner": {"discovery": 0.5}}
 }}
```

Removing a step reconnects whatever pointed at it to its first `next`.

## Edge-case keys (for `handles`)

Whole flow: `back_button`, `refresh_midflow`, `deep_link_midflow`, `session_expired`, `two_tabs`, `permission_changed`, `interrupted_resume`, `returning_user`, `flag_off`, `keyboard_only`, `screen_reader`, `large_text`, `small_screen`, `timezone_boundary`.

By step type:
- `input`: `empty_input`, `invalid_format`, `max_length`, `special_chars`, `paste_formatted`, `boundary_numbers`, `duplicate_value`, `autofill`, `keyboard_covers_field`, `progress_lost`
- `external`: `offline`, `timeout`, `server_error`, `double_submit`, `partial_success`, `slow_response`, `stale_data`, `rate_limited`
- `wait`: `offline`, `never_completes`, `user_leaves`, `slow_response`
- `decision`: `no_option_fits`, `change_mind`, `default_bias`
- `view`: `empty_state`, `huge_list`, `long_text`, `loading_state`
- `success`: `no_confirmation`, `repeat_action`, `undo`, `next_step_unclear`, `others_not_told`

List a key only if the spec says what happens in that situation.

## Real data (CSV for `calibrate` and `score`)

```csv
id,entered,continued
entry:home_banner,10000,2900
open_sheet,3000,2400
review_items,2400,2150
```

A step row: users who reached the step, users who went on. An `entry:` row: users exposed, users who started.

## How the simulation decides (summary)

For each user at each step, in order: lacks a requirement → fallback or blocked; time is drawn around `time_s` (slower for low skill and poor network); an error may occur (retry depends on patience and `on_error`); then the chance of carrying on is

`sigmoid(6 × (pull − 0.75 × (effort cost + confusion cost + trust cost) − fatigue) + 1.2)`

where pull = 0.55·motivation + 0.25·value + 0.20·trust − 0.05 per error met; effort cost = effort × (1 − 0.6·skill); confusion cost = (1 − clarity) × (0.9 − 0.5·skill); trust cost = (1 − trust) × 0.5 on sensitive steps; fatigue = 0.04 per step done, plus a penalty past 60% of the time budget. A user who quits is tagged with the largest of those costs. The code is `shoal/sim.py`.

The reported ranges come from 24 replications; in each, effort, clarity and value move by up to ±0.1 and error and discovery rates by up to ±20%, to show how much the answer depends on the guesses.
