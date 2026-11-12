You are a senior growth analyst writing a 150-word weekly note for a marketing director.
RULES: use ONLY the numbers in the JSON below; do not invent causes; say 'associated with' not 'caused by' unless an experiment is cited; mention that the data are synthetic; flag open items and anomalies; end with two concrete next steps.

FACTS (JSON):
```json
{
  "window": "last 8 weeks (through the week starting 2025-12-22) vs the previous 8 weeks",
  "data_label": "SYNTHETIC DATA",
  "data_end_date": "2025-12-28",
  "channels": [
    {
      "channel": "affiliate",
      "spend_recent": 10938.5,
      "customers_recent": 16.0,
      "cac_recent": 683.65625,
      "spend_change": 0.13204169051283143,
      "customers_change": -0.33333333333333337,
      "cac_change": 0.6980625357692471
    },
    {
      "channel": "direct",
      "spend_recent": 0.0,
      "customers_recent": 124.0,
      "cac_recent": null,
      "spend_change": null,
      "customers_change": 0.20388349514563098,
      "cac_change": null
    },
    {
      "channel": "display",
      "spend_recent": 20641.21,
      "customers_recent": 14.0,
      "cac_recent": 1474.3721428571428,
      "spend_change": 0.5153515791328351,
      "customers_change": 0.07692307692307687,
      "cac_change": 0.40711218062334686
    },
    {
      "channel": "email",
      "spend_recent": 0.0,
      "customers_recent": 31.0,
      "cac_recent": null,
      "spend_change": null,
      "customers_change": -0.515625,
      "cac_change": null
    },
    {
      "channel": "organic_search",
      "spend_recent": 0.0,
      "customers_recent": 157.0,
      "cac_recent": null,
      "spend_change": null,
      "customers_change": 0.08275862068965512,
      "cac_change": null
    },
    {
      "channel": "paid_search",
      "spend_recent": 30002.4,
      "customers_recent": 94.0,
      "cac_recent": 319.1744680851064,
      "spend_change": -0.32001500380194525,
      "customers_change": -0.29323308270676696,
      "cac_change": -0.037893569209135336
    },
    {
      "channel": "paid_social",
      "spend_recent": 35223.48,
      "customers_recent": 33.0,
      "cac_recent": 1067.378181818182,
      "spend_change": 0.17535168640630872,
      "customers_change": -0.2325581395348837,
      "cac_change": 0.53151886410519
    },
    {
      "channel": "referral",
      "spend_recent": 0.0,
      "customers_recent": 32.0,
      "cac_recent": null,
      "spend_change": null,
      "customers_change": -0.33333333333333337,
      "cac_change": null
    }
  ],
  "anomalies": [
    {
      "week_start": "2025-07-07",
      "metric": "paid spend",
      "z_score_vs_trailing_12w": -2.89
    },
    {
      "week_start": "2025-09-08",
      "metric": "paid spend",
      "z_score_vs_trailing_12w": 4.38
    },
    {
      "week_start": "2025-07-28",
      "metric": "paid customers",
      "z_score_vs_trailing_12w": -2.66
    },
    {
      "week_start": "2025-09-22",
      "metric": "paid customers",
      "z_score_vs_trailing_12w": 3.24
    }
  ],
  "open_items": [
    "EXP-002: Inconclusive: no significant effect. The data cannot distinguish zero from effects up to about +10% relative.",
    "EXP-003: Inconclusive: no significant effect. The data cannot distinguish zero from effects up to about +61% relative."
  ],
  "mmm_diagnostics_flagged": [
    "Durbin-Watson",
    "Ljung-Box p (8 lags)",
    "Breusch-Pagan p"
  ]
}
```
A human must verify every figure against the dashboard before this is shared.
