"""Reproducible SYNTHETIC SaaS data generator.

Story: a fictional B2B subscription SaaS company. Paid media buys clicks with
diminishing returns; visitors take multi-session journeys; some sign up, start
a 14-day trial and convert to a monthly subscription that churns over time.

Everything is driven by one numpy Generator seeded from GenConfig.seed, so the
same seed always gives identical tables.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import assumptions as A
from .assumptions import GenConfig


# ----------------------------------------------------------------- helpers
def add_months(dates: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Vectorised 'date + k months' that clips the day to the month length
    (2024-01-31 + 1 month = 2024-02-29), same as BigQuery/DuckDB."""
    dates = dates.astype("datetime64[D]")
    m0 = dates.astype("datetime64[M]")
    day = (dates - m0.astype("datetime64[D]")).astype(int)
    m1 = m0 + np.asarray(k).astype("timedelta64[M]")
    mlen = ((m1 + 1).astype("datetime64[D]") - m1.astype("datetime64[D]")).astype(int)
    return m1.astype("datetime64[D]") + np.minimum(day, mlen - 1).astype("timedelta64[D]")


def _adstock(x: np.ndarray, decay: float) -> np.ndarray:
    out = np.zeros_like(x, dtype=float)
    carry = 0.0
    for i, v in enumerate(x):
        carry = v + decay * carry
        out[i] = carry
    return out


def _random_times(rng, dates: np.ndarray) -> pd.DatetimeIndex:
    hour_p = np.array([1, 1, 1, 1, 1, 2, 3, 5, 8, 10, 11, 10, 9, 10, 11, 10, 9, 7, 6, 5, 4, 3, 2, 1], float)
    hour_p /= hour_p.sum()
    hours = rng.choice(24, size=len(dates), p=hour_p)
    secs = rng.integers(0, 3600, size=len(dates))
    return pd.to_datetime(dates) + pd.to_timedelta(hours * 3600 + secs, unit="s")


# ----------------------------------------------------------------- main
def generate(cfg: GenConfig | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or GenConfig()
    rng = np.random.default_rng(cfg.seed)
    days = pd.date_range(cfg.start_date, cfg.end_date, freq="D")
    D = len(days)
    n_weeks = D // 7
    week_idx = np.arange(D) // 7
    yrs = np.arange(D) / 365.25
    dow = days.dayofweek.values
    demand = np.array(A.MONTH_DEMAND)[days.month.values - 1]

    # ---------------- dimension tables
    channels = pd.DataFrame(
        [(f"ch_{n}", n, g, p) for n, g, p in A.CHANNEL_NAMES],
        columns=["channel_id", "channel_name", "channel_group", "is_paid"],
    )
    plans = pd.DataFrame(A.PLANS, columns=["plan_id", "plan_name", "monthly_price_usd"])
    start0 = days[0]
    camp_rows = []
    for cid, (ch, name, obj, _s, _c, _q, sw, ew) in A.CAMPAIGNS.items():
        s = start0 + pd.Timedelta(days=7 * sw)
        e = None if ew is None else start0 + pd.Timedelta(days=7 * ew - 1)
        camp_rows.append((cid, f"ch_{ch}", name, obj, s.date(), None if e is None else e.date()))
    campaigns = pd.DataFrame(camp_rows, columns=["campaign_id", "channel_id", "campaign_name", "objective",
                                                 "start_date", "end_date"])
    promo_rows, promo_flag = [], np.zeros(D)
    for y in sorted(set(days.year)):
        for i, (nm, (m1, d1), (m2, d2)) in enumerate(A.PROMOS):
            s, e = pd.Timestamp(y, m1, d1), pd.Timestamp(y, m2, d2)
            if e < days[0] or s > days[-1]:
                continue
            promo_rows.append((f"promo_{y}_{i + 1}", nm, s.date(), e.date()))
            promo_flag[(days >= s) & (days <= e)] = 1
    promotions = pd.DataFrame(promo_rows, columns=["promo_id", "promo_name", "start_date", "end_date"])

    # ---------------- paid spend, clicks, impressions
    base_spend, base_cpc = cfg.d("base_daily_spend"), cfg.d("base_cpc")
    elast, ctr = cfg.d("cpc_spend_elasticity"), cfg.d("ctr")
    cids = list(A.CAMPAIGNS)
    dow_w = np.array([1.10, 1.10, 1.05, 1.05, 1.00, 0.85, 0.85])
    dow_w = dow_w / dow_w.mean()
    weekly_budget = {}
    for ch in A.PAID:
        x = np.zeros(n_weeks)
        for t in range(1, n_weeks):
            x[t] = cfg.flight_phi * x[t - 1] + rng.normal(0, cfg.flight_sigma)
        mult = np.exp(x - 0.5 * x.var())
        u = rng.random(n_weeks)
        mult = np.where(u < cfg.burst_prob, mult * 1.8, np.where(u < cfg.burst_prob + cfg.pause_prob, mult * 0.35, mult))
        seasonal_plan = 1 + 0.12 * np.sin(2 * np.pi * (np.arange(n_weeks) - 8) / 52)
        growth = (1 + cfg.spend_growth_per_year) ** (np.arange(n_weeks) / 52)
        weekly_budget[ch] = base_spend[ch] * 7 * growth * mult * seasonal_plan

    spend_parts = []
    for cid in cids:
        ch, _n, _o, share, cpc_m, _q, sw, ew = A.CAMPAIGNS[cid]
        active = (week_idx >= sw) & ((week_idx < ew) if ew is not None else True)
        # re-normalise shares among campaigns active that day
        act_share = sum(A.CAMPAIGNS[c][3] * ((week_idx >= A.CAMPAIGNS[c][6]) &
                        ((week_idx < A.CAMPAIGNS[c][7]) if A.CAMPAIGNS[c][7] is not None else True))
                        for c in cids if A.CAMPAIGNS[c][0] == ch)
        norm_share = np.where(active, share / np.maximum(act_share, 1e-9), 0.0)
        spend = (weekly_budget[ch][week_idx] / 7) * dow_w[dow] * norm_share * rng.lognormal(0, 0.08, D)
        ref = base_spend[ch] * share
        cpc = (base_cpc[ch] * cpc_m * (1 + cfg.cpc_inflation_per_year) ** yrs
               * np.power(np.maximum(spend, 1e-6) / ref, elast[ch]) * rng.lognormal(0, 0.06, D)
               * (1 + 0.08 * np.cos(2 * np.pi * (days.dayofyear.values - 330) / 365)))
        clicks = rng.poisson(np.where(active, spend / cpc, 0))
        imps = np.round(clicks / (ctr[ch] * rng.lognormal(0, 0.08, D))).astype(int)
        part = pd.DataFrame({"spend_date": days, "campaign_id": cid, "channel_id": f"ch_{ch}",
                             "spend_usd": np.round(spend, 2), "impressions": imps, "clicks": clicks})
        spend_parts.append(part[active])
    ad_spend = pd.concat(spend_parts, ignore_index=True).sort_values(["spend_date", "campaign_id"]).reset_index(drop=True)
    ad_spend["spend_date"] = ad_spend["spend_date"].dt.date

    # ---------------- overhead (fully loaded CAC)
    months = pd.date_range(days[0].replace(day=1), days[-1], freq="MS")
    spend_by_month = ad_spend.assign(m=pd.to_datetime(ad_spend.spend_date).dt.to_period("M").dt.to_timestamp()).groupby("m").spend_usd.sum()
    oh = []
    for i, m in enumerate(months):
        grow = (1 + 0.10) ** (i / 12)
        sp = float(spend_by_month.get(m, 0.0))
        oh += [(m.date(), "team_salaries", round(9000 * grow, 2)),
               (m.date(), "tools", round(1400 * grow * rng.uniform(0.95, 1.05), 2)),
               (m.date(), "agency_fees", round(0.08 * sp, 2)),
               (m.date(), "creative_production", round(rng.uniform(1200, 3000), 2))]
    overhead = pd.DataFrame(oh, columns=["month_start", "cost_category", "cost_usd"])

    # ---------------- new visitors (first sessions)
    spend_wide = ad_spend.pivot_table(index="spend_date", columns="channel_id", values="spend_usd", aggfunc="sum").reindex(days.date).fillna(0)
    halo_in = (spend_wide["ch_paid_social"].values / (base_spend["paid_social"]) * 0.6
               + spend_wide["ch_display"].values / (base_spend["display"]) * 0.4)
    halo_idx = _adstock(halo_in, cfg.halo_decay_per_day) * (1 - cfg.halo_decay_per_day)
    halo_mult = 1 + cfg.halo_strength * (np.power(np.maximum(halo_idx, 0.01), 0.6) - 1)

    ad_spend["sessions"] = rng.binomial(ad_spend["clicks"].astype(int), cfg.click_to_session_rate)
    first_rows = []
    for _, r in ad_spend[ad_spend.sessions > 0].iterrows():
        first_rows.append((r.spend_date, r.channel_id[3:], r.campaign_id, int(r.sessions)))
    paid_first = pd.DataFrame(first_rows, columns=["d", "channel", "campaign_id", "n"])
    brand_by_day = ad_spend[ad_spend.campaign_id == "ps_brand"].set_index("spend_date")["sessions"].reindex(days.date).fillna(0).values

    free_base = cfg.d("free_daily_visitors")
    free_parts = []
    for ch in A.FREE:
        lam = free_base[ch] * cfg.scale * demand * (1 + cfg.free_growth_per_year) ** yrs
        if ch in ("organic_search", "direct"):
            lam = lam * halo_mult
        if ch == "organic_search":
            lam = np.maximum(lam - cfg.brand_displacement * brand_by_day, 0.4 * lam)
        free_parts.append(pd.DataFrame({"d": days.date, "channel": ch, "campaign_id": None, "n": rng.poisson(lam)}))
    first = pd.concat([paid_first.assign(n=lambda x: np.round(x.n * cfg.scale).astype(int)), *free_parts], ignore_index=True)
    first = first[first.n > 0]
    fs = first.loc[first.index.repeat(first.n), ["d", "channel", "campaign_id"]].reset_index(drop=True)
    fs["ts"] = _random_times(rng, pd.to_datetime(fs.d).values)
    fs = fs.sort_values("ts").reset_index(drop=True)
    N = len(fs)
    fs["vidx"] = np.arange(N)
    fs["device_category"] = rng.choice(["desktop", "mobile", "tablet"], size=N, p=[0.62, 0.32, 0.06])
    fs["ordinal"] = 0

    # ---------------- extra (return) sessions
    lam_extra = cfg.d("extra_session_lambda")
    n_extra = np.minimum(rng.poisson(fs.channel.map(lam_extra).values), 5)
    ex = fs.loc[fs.index.repeat(n_extra), ["vidx", "ts", "device_category"]].rename(columns={"ts": "first_ts"}).reset_index(drop=True)
    gaps = 1 + np.floor(rng.exponential(4.0, size=len(ex)))
    ex["gap"] = gaps
    ex["ordinal"] = ex.groupby("vidx").cumcount() + 1
    ex["cum_gap"] = ex.groupby("vidx")["gap"].cumsum()
    ex = ex[ex.cum_gap <= cfg.max_journey_days].copy()
    ex["ts"] = ex.first_ts + pd.to_timedelta(ex.cum_gap, unit="D") + pd.to_timedelta(rng.integers(-6 * 3600, 6 * 3600, size=len(ex)), unit="s")
    ex = ex[ex.ts <= pd.Timestamp(cfg.end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)].copy()
    mix_names, mix_p = zip(*cfg.return_channel_mix)
    ex["channel"] = rng.choice(mix_names, size=len(ex), p=np.array(mix_p) / sum(mix_p))
    ex["campaign_id"] = None
    sess = pd.concat([fs[["vidx", "ordinal", "ts", "channel", "campaign_id", "device_category"]],
                      ex[["vidx", "ordinal", "ts", "channel", "campaign_id", "device_category"]]], ignore_index=True)
    sess = sess.sort_values(["vidx", "ts"]).reset_index(drop=True)
    sess["ordinal"] = sess.groupby("vidx").cumcount()

    # ---------------- who converts, and in which session
    first_info = fs.set_index("vidx")
    sess["first_channel"] = sess.vidx.map(first_info["channel"])
    sess["first_campaign"] = sess.vidx.map(first_info["campaign_id"])
    w_ord = np.array([1.0, 1.3, 1.7, 2.2, 2.8, 3.4])
    score = np.log(w_ord[np.minimum(sess.ordinal.values, 5)]) + rng.gumbel(size=len(sess))
    sess["score"] = score
    dec_idx = sess.groupby("vidx")["score"].idxmax()
    dec = sess.loc[dec_idx.values].set_index("vidx")
    quality = {cid: v[5] for cid, v in A.CAMPAIGNS.items()}
    camp_q = dec.first_campaign.map(quality).fillna(1.0).values
    base = dec.first_channel.map(cfg.d("signup_base")).values
    dev_mult = dec.device_category.map({"desktop": 1.15, "mobile": 0.6, "tablet": 0.9}).values
    d_date = dec.ts.dt.floor("D")
    d_idx = ((d_date - pd.Timestamp(cfg.start_date)).dt.days.values).clip(0, D - 1)
    season = demand[d_idx] ** 0.5
    promo = np.where(promo_flag[d_idx] == 1, cfg.promo_signup_multiplier, 1.0)
    het = rng.lognormal(-0.32, 0.8, size=len(dec))
    boost = 1 + 0.18 * np.minimum(dec.ordinal.values, 3)
    p_sign = np.clip(base * camp_q * season * promo * dev_mult * het * boost * 1.0, 0, 0.6)
    converts = rng.random(len(dec)) < p_sign
    dec["converts"] = converts
    sess["is_decision"] = False
    sess.loc[dec_idx.values, "is_decision"] = True
    sess["converts"] = sess.vidx.map(dec["converts"])
    # drop sessions after the signup session for converters
    dec_ord = sess.vidx.map(dec["ordinal"])
    sess = sess[~(sess.converts & (sess.ordinal > dec_ord))].reset_index(drop=True)

    # ---------------- ids
    sess = sess.sort_values("ts").reset_index(drop=True)
    sess["session_id"] = [f"s{i:08d}" for i in range(1, len(sess) + 1)]
    vmap = {v: f"v{i:07d}" for i, v in enumerate(sorted(sess.vidx.unique()), start=1)}
    sess["visitor_id"] = sess.vidx.map(vmap)
    sess["channel_id"] = "ch_" + sess.channel

    # ---------------- funnel events
    pr_base = sess.channel.map({"paid_search": 0.14, "paid_social": 0.09, "display": 0.06, "affiliate": 0.12,
                                "organic_search": 0.14, "email": 0.20, "referral": 0.15, "direct": 0.22}).values
    is_dec = sess.is_decision.values
    conv = sess.converts.values.astype(bool)
    r1, r2 = rng.random(len(sess)), rng.random(len(sess))
    pricing = np.where(is_dec & conv, True, np.where(is_dec, r1 < 0.32 + pr_base, r1 < pr_base))
    sstart = np.where(is_dec & conv, True, pricing & (r2 < np.where(is_dec, 0.26, 0.12)))
    signup = is_dec & conv
    ev = []
    t0 = sess.ts.values
    off1 = rng.integers(20, 240, size=len(sess))
    off2 = off1 + rng.integers(40, 400, size=len(sess))
    off3 = off2 + rng.integers(60, 300, size=len(sess))
    for name, mask, off in (("view_pricing", pricing, off1), ("signup_start", sstart, off2), ("signup_complete", signup, off3)):
        e = pd.DataFrame({"session_id": sess.session_id[mask].values, "visitor_id": sess.visitor_id[mask].values,
                          "event_ts": t0[mask] + off[mask].astype("timedelta64[s]"), "event_name": name})
        ev.append(e)

    # ---------------- customers
    sc = ev[2].copy().sort_values("event_ts").reset_index(drop=True)
    sc["customer_id"] = [f"c{i:07d}" for i in range(1, len(sc) + 1)]
    first_touch_ch = sess[sess.ordinal == 0].set_index("visitor_id")["channel"]
    first_touch_camp = sess[sess.ordinal == 0].set_index("visitor_id")["campaign_id"]
    sc["first_channel"] = sc.visitor_id.map(first_touch_ch)
    sc["first_campaign"] = sc.visitor_id.map(first_touch_camp)
    # a few visitors' first sessions are not in sess? (never: ordinal 0 always kept)
    customers = pd.DataFrame({"customer_id": sc.customer_id, "visitor_id": sc.visitor_id, "signup_ts": sc.event_ts})
    customers["country"] = rng.choice(["US", "GB", "DE", "CA", "AU", "FR", "NG", "IN"], size=len(customers),
                                      p=[0.50, 0.12, 0.08, 0.08, 0.05, 0.05, 0.04, 0.08])
    customers["segment"] = rng.choice(["smb", "mid_market", "enterprise"], size=len(customers), p=[0.60, 0.30, 0.10])
    # trial start
    has_trial = rng.random(len(sc)) < cfg.trial_start_rate
    trial = sc[has_trial].copy()
    trial["event_ts"] = trial.event_ts + pd.to_timedelta(rng.integers(1, 6, size=len(trial)), unit="s")
    trial["event_name"] = "trial_start"
    events = pd.concat([ev[0].assign(customer_id=None), ev[1].assign(customer_id=None),
                        sc[["session_id", "visitor_id", "event_ts", "event_name", "customer_id"]], 
                        trial[["session_id", "visitor_id", "event_ts", "event_name", "customer_id"]]], ignore_index=True)
    events = events.sort_values(["event_ts", "event_name"]).reset_index(drop=True)
    events.insert(0, "event_id", np.arange(1, len(events) + 1))
    events = events[["event_id", "session_id", "visitor_id", "customer_id", "event_ts", "event_name"]]

    # ---------------- subscriptions
    p_paid = (trial.first_channel.map(cfg.d("trial_to_paid")).values
              * np.power(trial.first_campaign.map(quality).fillna(1.0).values, 0.3)
              * rng.lognormal(-0.02, 0.2, size=len(trial)))
    pays = rng.random(len(trial)) < np.clip(p_paid, 0, 0.9)
    sub = trial[pays].copy()
    early = rng.random(len(sub)) < 0.15
    lag = np.where(early, rng.integers(3, cfg.trial_days, size=len(sub)), cfg.trial_days)
    sub["start_date"] = (sub.event_ts.dt.floor("D") + pd.to_timedelta(lag, unit="D")).values.astype("datetime64[D]")
    sub = sub[sub.start_date <= np.datetime64(cfg.end_date)].copy()
    plan_ids = [p[0] for p in A.PLANS]
    plan_choice = np.empty(len(sub), dtype=object)
    for ch, probs in A.PLAN_MIX.items():
        m = (sub.first_channel == ch).values
        plan_choice[m] = rng.choice(plan_ids, size=m.sum(), p=probs)
    sub["plan_id"] = plan_choice
    price = sub.plan_id.map({p[0]: p[2] for p in A.PLANS}).values
    coupon = (sub.first_campaign == "af_coupon").values
    sd = sub.event_ts.dt.floor("D")
    in_promo = np.array([promo_flag[max(0, min(D - 1, (x - pd.Timestamp(cfg.start_date)).days))] for x in sd]) == 1
    promo_disc = in_promo & (rng.random(len(sub)) < 0.6)
    disc_pct = np.where(coupon, 0.25, np.where(promo_disc, 0.20, 0.0))
    disc_cycles = np.where(coupon, 3, np.where(promo_disc, 2, 0))
    sub = sub.reset_index(drop=True)
    sub["subscription_id"] = [f"sub{i:07d}" for i in range(1, len(sub) + 1)]
    sub["discount_pct"], sub["discount_cycles"] = disc_pct, disc_cycles
    # churn simulation over billing cycles
    start = sub.start_date.values.astype("datetime64[D]")
    end_np = np.datetime64(cfg.end_date)
    max_cycle = 0
    while add_months(start, np.full(len(start), max_cycle + 1)).min() <= end_np:
        max_cycle += 1
        if max_cycle > 60:
            break
    floor_h = sub.plan_id.map(cfg.d("monthly_churn_floor")).values * sub.first_channel.map(cfg.d("churn_channel_mult")).values
    alive = np.ones(len(sub), bool)
    churn_cycle = np.full(len(sub), -1)
    cancel_date = np.full(len(sub), np.datetime64("NaT"), dtype="datetime64[D]")
    for k in range(1, max_cycle + 2):
        pay_k = add_months(start, np.full(len(start), k))
        pay_prev = add_months(start, np.full(len(start), k - 1))
        h = floor_h * (1 + cfg.early_churn_boost * np.exp(-(k - 1) / cfg.early_churn_tau))
        drew = alive & (pay_prev <= end_np)
        churn_now = drew & (rng.random(len(sub)) < h)
        span = np.maximum((pay_k - pay_prev).astype(int) - 1, 1)
        cd = pay_prev + (1 + (rng.random(len(sub)) * span).astype(int)).astype("timedelta64[D]")
        # cancel requests only visible if on/before data end
        visible = churn_now & (cd <= end_np)
        # churn after the data window is not observable -> customer stays "active"
        churn_cycle = np.where(visible & alive, k, churn_cycle)
        cancel_date = np.where(visible & alive, cd, cancel_date)
        alive = alive & ~visible
    sub["cancel_date"] = cancel_date
    sub["end_date"] = np.where(churn_cycle > 0, add_months(start, np.maximum(churn_cycle, 0)), np.datetime64("NaT")).astype("datetime64[D]")
    subscriptions = sub[["subscription_id", "customer_id", "plan_id", "start_date", "cancel_date", "end_date",
                         "discount_pct", "discount_cycles"]].copy()

    # ---------------- payments & refunds
    n_cycles = np.where(churn_cycle > 0, churn_cycle, max_cycle + 1)  # cycles 0..n-1 may be paid
    rows = sub.loc[sub.index.repeat(n_cycles)].reset_index(drop=True)
    rows["billing_cycle_number"] = rows.groupby("subscription_id").cumcount()
    rows["payment_date"] = add_months(rows.start_date.values, rows.billing_cycle_number.values)
    rows = rows[rows.payment_date <= end_np].copy()
    base_price = rows.plan_id.map({p[0]: p[2] for p in A.PLANS}).values
    disc = np.where(rows.billing_cycle_number.values < rows.discount_cycles.values, 1 - rows.discount_pct.values, 1.0)
    rows["gross_amount_usd"] = np.round(base_price * disc, 2)
    rows["currency"] = "USD"
    rows = rows.sort_values(["payment_date", "subscription_id"]).reset_index(drop=True)
    rows["payment_id"] = [f"pay{i:08d}" for i in range(1, len(rows) + 1)]
    payments = rows[["payment_id", "subscription_id", "customer_id", "payment_date", "billing_cycle_number",
                     "gross_amount_usd", "currency"]].copy()
    pr = np.where(rows.billing_cycle_number.values == 0, cfg.refund_prob_first_payment, cfg.refund_prob_renewal)
    refunded = rng.random(len(rows)) < pr
    rf = rows[refunded].copy()
    rf["refund_date"] = rf.payment_date.values + rng.integers(2, 26, size=len(rf)).astype("timedelta64[D]")
    rf = rf[rf.refund_date <= end_np].copy()
    full = rng.random(len(rf)) < 0.7
    rf["refund_amount_usd"] = np.round(np.where(full, rf.gross_amount_usd, rf.gross_amount_usd * 0.5), 2)
    rf["refund_id"] = [f"ref{i:07d}" for i in range(1, len(rf) + 1)]
    refunds = rf[["refund_id", "payment_id", "refund_date", "refund_amount_usd"]].copy()

    # ---------------- sessions output
    sessions = sess[["session_id", "visitor_id", "session_ts" if False else "ts", "channel_id", "campaign_id", "device_category"]].rename(columns={"ts": "session_ts"})
    sessions = sessions.sort_values("session_ts").reset_index(drop=True)

    out = {
        "channels": channels, "campaigns": campaigns,
        "ad_spend_daily": ad_spend[["spend_date", "campaign_id", "channel_id", "spend_usd", "impressions", "clicks"]],
        "marketing_overhead_monthly": overhead, "promotions": promotions, "plans": plans,
        "sessions": sessions, "events": events, "customers": customers, "subscriptions": subscriptions,
        "payments": payments, "refunds": refunds,
    }
    from .experiments import generate_experiments
    cat, assign, truth = generate_experiments(cfg)
    out["experiment_catalog"], out["experiment_assignments"] = cat, assign
    from .extra_experiments import generate_geo, generate_lifecycle
    gcat, gout, gtruth = generate_geo(cfg)
    lcat, lusers, ltruth = generate_lifecycle(cfg)
    out.update({"geo_experiment_catalog": gcat, "geo_daily_outcomes": gout,
                "lifecycle_experiment_catalog": lcat, "lifecycle_experiment_users": lusers})
    truth = {**truth, "GEO-001": gtruth, "LIFE-001": ltruth}
    out["_ground_truth"] = truth  # type: ignore[assignment]
    return out
