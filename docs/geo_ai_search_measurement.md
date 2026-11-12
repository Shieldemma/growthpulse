# GEO / AI-search measurement framework (design only — NOT implemented)

> No code, data or results exist for this in the project. It is a measurement *design* you can discuss and later implement.

**Problem.** Visits and customers influenced by answers in LLM answer engines often arrive as *direct*, *branded organic* or an un-tagged referral, so UTM-based attribution structurally under-counts them.

## Metrics
| Layer | Metric | Source | Caveat |
|---|---|---|---|
| Visibility | **Share of voice (SoV)** = brand mentions / mentions of all tracked brands over a fixed prompt panel, per engine and prompt cluster | scheduled prompt panel (e.g. 200 prompts x engines x weekly), logged answers | answers are non-deterministic: run each prompt several times, report mean + interval; version the panel |
| Visibility | citation rate (our domain cited), position, sentiment, accuracy of claims | same | needs human spot-checks |
| Traffic (observed) | sessions with referrer domains of answer engines, `utm_source` conventions where the engine appends one | server-side events | a minority of AI-driven visits carry a referrer |
| Traffic (modelled) | **AI-influenced uplift** in direct + branded-organic sessions | model below | an estimate with uncertainty, never an observed fact |
| Outcome | signups/customers/revenue from AI-referred sessions; assisted conversions | warehouse | small counts at first |

## Attribution design
1. **Capture** referrer domain and landing-page patterns server-side; maintain a `dim_referrer` mapping (engine, type).
2. **Panel -> time series**: weekly SoV by engine. Join to weekly direct + branded-organic sessions and to observed AI-referral sessions.
3. **Modelled contribution**: regression / Bayesian structural time-series of direct+branded sessions on lagged SoV with controls (seasonality, paid spend, PR/launch dummies, brand-search volume); report incremental sessions with intervals. Include a **placebo** (non-AI-exposed geography/language or an unrelated keyword set) to check the model is not just picking up trend.
4. **Validation by intervention**: ship a content/structured-data change on a subset of pages or topics (staggered rollout) and compare SoV and traffic for treated vs untreated clusters (difference-in-differences, as in `geo_lift.py`), because correlation between SoV and traffic is confounded by overall brand momentum.
5. **Reporting**: SoV trend, referred sessions, modelled uplift range, and an explicit "unmeasured share" statement; feed the modelled estimate into the MMM as a separate, clearly-labelled control or channel only once validated.

## Risks
Panel bias (prompt choice), engine changes, personalised answers, attribution double-counting with brand search/direct, and false precision — always show intervals and the method label "modelled".
