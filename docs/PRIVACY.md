# Privacy (as implemented)

This describes what MatchKite **currently does in code**. It is not a legal opinion, a controller/processor register, or a claim about GDPR, ICO, or any other regime.

MatchKite is a non-commercial careers-guidance demo for Bristol and Gloucestershire. It is not an official careers, counselling, or crisis service. There are no user accounts.

The in-app copy lives at `web/src/app/privacy/page.tsx`. Where that page disagrees with the API or libraries, **this document follows the code** and notes the difference.

## Age bands and under-16

Age is a **self-declared band** (`under_16`, `16_17`, `18_24`, `25_plus`, `prefer_not`). Identity documents are not collected or checked (`safeguarding.py`).

- **Under 16:** `/match` returns HTTP 403. The intake UI hides the rest of the form and points people to a parent, carer, teacher, or careers adviser.
- **Prefer not to say:** matching is allowed. OpenAI briefings and Gemini plans are forced off (`age_band_allows_ai` is false).
- **16–17, 18–24, 25+:** matching is allowed. AI features are allowed only if the corresponding intake flags are on.
- **16–17 extra tick:** the web form asks for an extra “guidance only” confirmation before submit if AI is on. That tick is **not sent to or enforced by the API**.
- Military pathway cards may show an under-18 notice for `16_17`, `prefer_not`, empty, or `under_16` bands.

## What is processed for a match

`POST /match` accepts the intake payload (`api/main.py` `MatchRequest` / `IntakeForm`):

- Age band, leaver type, location, qualification level, availability
- Interests, courses, passions, work-experience chips
- Optional free text: goal (160 chars) and proud example (500 chars)
- Optional chips: barriers, must-haves, support available, apply-readiness
- Optional `psych_answers` (the current web form always sends `{}`)
- Flags: `use_openai_briefing`, `use_gemini_plan`, `allow_anonymous_logging`

The matcher builds an in-memory leaver profile (including `profile_text`) and returns ranked matches plus persona fields. Results are held in **browser React state** until the page is refreshed. The API does not create a user record.

Optional health/disability-style barrier chips are used for matching only. Copy states they are not medical advice.

## What is not collected

There are **no fields** for name, email, phone, address, or login. The demo does not require contact details.

Free-text boxes are not scanned for contact details. If someone types them, they travel with that request (and to an LLM if AI is on).

Anonymous live-learning rows **do not** store name, contact details, age band, location, free text, barriers, or chat.

## Anonymous live learning

`allow_anonymous_logging` defaults to **true** on both the form checkbox and the API. Uncheck it before submit to skip logging.

If left on, a successful match may append one JSONL event to `data/live/leavers_events.jsonl` (`live_learning.py`): event id, timestamp, channel (`web:work` / `web:education` / `web:military`), interest sectors, RIASEC codes/scores if present, assigned persona / cluster / method, compact persona-fit, leaver type. Empty events (no sectors and no RIASEC) are not written.

`POST /feedback/persona` can later set `persona_helpful` and `feedback_at` on that event id.

Events can be merged into clustering training (`DATA.md`, `scripts/08_3_merge_live_into_curated.py`). Docker persists `data/live/` on a named volume. The file is gitignored.

## Retention

Live events older than **180 days** are pruned when a new event is appended. Operators can change this with `LIVE_EVENTS_RETENTION_DAYS` (minimum 1). Rows with unparseable timestamps are kept.

Match requests, plan/chat bodies, and TTS text are **not** written to that JSONL file. This repo does not define retention for host HTTP logs or for OpenAI / Google.

## LLM opt-in (OpenAI and Gemini)

**Match reports (OpenAI).** `use_openai_briefing` defaults to **false**. The UI checkbox is off. The server also turns it off if the age band is not 16+ or if intake free text hits the safety screen. When on, `generate_briefing` sends leaver `profile_text` (age band, location, courses, interests, optional goal/proud/barriers/etc.) plus matched employer, course, or military context to OpenAI (`OPENAI_MODEL`, default `gpt-4o-mini`).

**Action plans (Gemini).** `use_gemini_plan` defaults to **false** on `/match`. Plan endpoints (`/plan/generate`, `/plan/breakdown`, `/plan/chat`) refuse the call unless `use_gemini_plan` is true **and** the leaver age band allows AI. When on, Gemini receives intake-style leaver fields (including optional free text), the selected match, plan steps, and chat. If `GEMINI_API_KEY` is missing, templates run locally and nothing is sent.

The web client only calls plan endpoints after `/match` returned `plans_enabled`. Those Pydantic models default `use_gemini_plan` to **true** if a raw API client omits the field — unlike `/match`.

**Read aloud (OpenAI Speech).** `POST /tts` sends the posted text to OpenAI TTS. It has **no** age-band or briefing-consent flag. The UI tries OpenAI first, then the browser `speechSynthesis` API. “Read aloud” is shown on catalogue summaries even when briefing opt-in is off (those strings are match copy, not intake). If a briefing was generated, that personalised markdown can be sent too.

`/privacy` does not mention TTS.

## Safeguarding routing

Keyword regexes in `safeguarding.py` (self-harm, suicide, abuse, grooming, immediate danger, and similar). Prefer false positives. This is not a classifier and not a crisis service.

- **Intake:** only `proud_example` and `goal_sentence` are screened. On a hit, those two fields are cleared, both LLM flags are forced off, matching continues offline, and the UI can show the fixed help block (`safety_referral_suggested`).
- **Chat:** only the **current** message is screened. On a hit, the API returns fixed markdown (999, Childline 0800 1111, Samaritans 116 123) with `source: "safeguarding"` and does **not** call Gemini for that turn. Chat history is not keyword-screened. Crisis strings are not stored in the live-learning file.

See `/help` for the same contacts. Referral copy is editorial, not model-generated.

## Open-data attribution

Employer and course context in the product is built from public and curated sources. Licence text and limits: [DATA.md](../DATA.md).

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

- DfE — Apprenticeships statistics / Explore Education Statistics (underlying vacancies)
- Companies House — Basic Company Data product
- DfE — National Careers Service course directory (Gloucestershire / Bristol filter)

Also: curated seed CSVs and taxonomy in this repo; optional JobCannon psychometric files (CC-BY-4.0) for clustering training, not for identifying a person. Inclusion of an employer or course is not an endorsement. Vacancy and course rows are not guaranteed live.

## `/privacy` page vs code

| Topic | In-app page | Code |
| --- | --- | --- |
| Anonymous logging | “When you opt in” / opt out before submit | Checkbox and API default **on** |
| Action plans off by default | Yes | True for `/match` and the form; `/plan/*` defaults the flag **on** if omitted |
| What is not collected | No name/email/phone required | Same fields; free text is not stripped |
| Chat | “Do not enter contact details” | No contact-detail filter; keyword safety screen only |
| TTS / Read aloud | Not mentioned | OpenAI Speech, ungated by briefing consent |
| 16–17 AI confirmation | Not mentioned | UI-only; not an API check |
| Data attribution | Points at `DATA.md` | File is repo-root `DATA.md` |

Last checked against the codebase: 2026-09-02.
