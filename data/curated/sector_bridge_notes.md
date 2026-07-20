# Occupation → Glos sector bridge

`occupation_to_sector.csv` maps common occupation titles (O*NET-style wording)
onto this project's `SECTORS` tags and a typical RIASEC interest profile.

## How rows are used

1. **JobCannon people** — match each person's RIASEC vector to nearest occupations,
   then union their `sectors` into `interest_sectors`.
2. **O*NET-only / offline** — sample occupations as synthetic leavers
   (`source=onet_bridge`) using the embedded R–I–A–S–E–C columns.
3. **Glos priors** — always mixed in so local pathways (aero, agri, cyber, care)
   are not washed out by online adult samples.

## Editing rules

- `sectors` = pipe-separated tags from `intake_options.yaml` / `personas.SECTORS`.
- Prefer 1–3 sectors per occupation; avoid dumping every tag.
- RIASEC columns are relative strengths (roughly 1–7 O*NET-style), not percentages.
- When adding UK-specific titles, keep `occupation_key` stable (slug).

## QA checklist

- [ ] Realistic-heavy rows can land on construction **or** agri **or** aero — not only one.
- [ ] Investigative + Conventional can hit cyber **and** business/finance.
- [ ] Social maps to health / education / public, not hospitality by default.
- [ ] Artistic prefers creative_events; Enterprising can add hospitality/retail/business.
