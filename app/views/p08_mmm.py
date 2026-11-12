import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from growthpulse import paths
from growthpulse.mmm import budget as B
from growthpulse.mmm.data import MEDIA
from lib import data, ui


def render():
    data.require_data()
    ui.header("Marketing Mix Modelling", "A weekly, regression-based MMM. It demonstrates the method on SYNTHETIC data: model estimates, not causal proof.")
    A = paths.ANALYTICS
    fit = data.table(A, "mmm_fit")
    if fit.empty:
        return ui.empty_state("No MMM results.", "Run the pipeline.")
    fit["week_start"] = pd.to_datetime(fit.week_start)
    meta = data.table(A, "mmm_meta").iloc[0]
    cmp_ = data.table(A, "mmm_model_comparison")
    summ = data.table(A, "mmm_channel_summary")
    contrib = data.table(A, "mmm_contrib_weekly")
    contrib["week_start"] = pd.to_datetime(contrib.week_start)
    scen = data.table(A, "mmm_budget_scenarios")
    curves = data.table(A, "mmm_response_curves")
    diag = data.table(A, "mmm_diagnostics")
    sens = data.table(A, "mmm_sensitivity")
    tabs = st.tabs(["1. Data & EDA", "2. Model comparison", "3. Fit & diagnostics", "4. Contributions", "5. Response curves", "6. Budget scenarios", "7. Director's guide"])
    with tabs[0]:
        st.markdown(f"**Outcome:** weekly *new MRR* (first-payment revenue of subscriptions started that week). **Inputs:** weekly spend for 4 paid channels, trend, 2 seasonal harmonics, promotion share. "
                    f"{int(meta.total_weeks_used)} weeks used after a 4-week burn-in. Sessions/signups are deliberately NOT inputs (they are downstream of media, which would bias channel effects).")
        w = data.table(paths.MARTS, "mart_mmm_weekly")
        w["week_start"] = pd.to_datetime(w.week_start)
        spend_cols = [c for c in w.columns if c.startswith("spend_") and c != "spend_total"]
        st.plotly_chart(px.area(w.melt(id_vars="week_start", value_vars=spend_cols), x="week_start", y="value", color="variable", title="Weekly spend by channel (USD)"), width="stretch")
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.line(w, x="week_start", y="new_mrr_usd", title="Outcome: weekly new MRR (USD)"), width="stretch")
        corr = w[spend_cols + ["new_mrr_usd"]].corr()
        c2.plotly_chart(px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, title="Correlation (collinearity check)"), width="stretch")
        st.caption("Low correlation between channels is what lets a regression separate their effects; budgets that always move together cannot be separated.")
    with tabs[1]:
        view = cmp_.copy()
        st.dataframe(view[["model", "test_rmse", "test_mae", "test_mape", "test_r2", "train_rmse", "cv_rmse", "chosen_for_decisions"]], width="stretch", hide_index=True)
        st.markdown(f"**Decision rule:** {meta.decision_rule}  \n**Chosen:** `{meta.chosen}`. Test = last {int(meta.test_weeks)} weeks, never used to fit or tune (hyper-parameters tuned with expanding-window cross-validation inside the {int(meta.train_weeks)} training weeks).")
        st.caption("A negative test R2 means the model predicted worse than simply using the test-period average. Compare models on test RMSE, and keep the simplest one that earns its complexity.")
    with tabs[2]:
        fig = go.Figure()
        fig.add_scatter(x=fit.week_start, y=fit.new_mrr_usd, name="Actual")
        fig.add_scatter(x=fit.week_start, y=fit.fitted, name="Fitted")
        t0 = fit[fit.is_test_period == 1].week_start.min()
        fig.add_vrect(x0=t0, x1=fit.week_start.max(), fillcolor="orange", opacity=0.12, line_width=0, annotation_text="held-out test period (fitted on all data after selection)")
        fig.update_layout(title="Actual vs fitted weekly new MRR", yaxis_title="USD")
        st.plotly_chart(fig, width="stretch")
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.scatter(fit, x="fitted", y="residual", title="Residuals vs fitted"), width="stretch")
        c2.plotly_chart(px.histogram(fit, x="residual", nbins=25, title="Residual distribution"), width="stretch")
        st.dataframe(diag, width="stretch", hide_index=True)
        warn = diag[diag.status != "ok"]
        if len(warn):
            st.warning("Diagnostics flagged: " + "; ".join(warn.check) + ". Treat intervals as optimistic and prefer conclusions that survive the sensitivity table.")
    with tabs[3]:
        s = summ.copy()
        st.dataframe(s[["channel", "total_spend_usd", "contribution_usd", "share_of_revenue", "share_p05", "share_p95", "avg_roi", "avg_roi_p05", "avg_roi_p95", "lag_weeks", "decay", "share_of_draws_at_zero", "marginal_weekly_mrr_per_extra_usd"]],
                     width="stretch", hide_index=True)
        ui.download(s, "mmm_channel_summary")
        long = contrib.melt(id_vars="week_start", var_name="component", value_name="usd")
        st.plotly_chart(px.area(long, x="week_start", y="usd", color="component", title="Decomposition of weekly new MRR"), width="stretch")
        fig = go.Figure(go.Bar(x=s.channel, y=s.share_of_revenue, error_y=dict(type="data", symmetric=False, array=s.share_p95 - s.share_of_revenue, arrayminus=s.share_of_revenue - s.share_p05)))
        fig.update_layout(title="Share of new MRR driven by each channel (90% bootstrap interval)", yaxis_tickformat=".0%")
        st.plotly_chart(fig, width="stretch")
        st.subheader("Sensitivity to modelling assumptions")
        sp = sens.copy()
        sp["abs_change"] = sp.change_in_share_of_revenue.abs()
        agg = sp.groupby("channel").agg(base_contribution=("base_contribution_usd", "first"), min_contribution=("contribution_usd", "min"), max_contribution=("contribution_usd", "max")).reset_index()
        st.dataframe(agg, width="stretch", hide_index=True)
        st.caption("Range of each channel's contribution when ONE adstock/saturation/lag assumption is changed at a time. Bootstrap intervals above do not include this uncertainty.")
        st.warning("**Uncertainty.** Intervals reflect coefficient noise only. A channel whose interval touches zero (or whose 'draws at zero' share is high) has no reliably estimated effect. "
                   "MMM estimates are associations after controlling for trend/seasonality/promotions; they become causal only if no important driver is omitted, and here they were fitted to synthetic data.")
    with tabs[4]:
        ch = st.selectbox("Channel", sorted(curves.channel.unique()))
        c = curves[curves.channel == ch]
        fig = go.Figure()
        fig.add_scatter(x=c.weekly_spend_usd, y=c.p95, line=dict(width=0), showlegend=False)
        fig.add_scatter(x=c.weekly_spend_usd, y=c.p05, fill="tonexty", line=dict(width=0), name="90% interval")
        fig.add_scatter(x=c.weekly_spend_usd, y=c.weekly_mrr, name="Estimated response")
        cur = float(summ.set_index("channel").loc[ch, "current_weekly_spend_usd"])
        fig.add_vline(x=cur, line_dash="dot", annotation_text="current (last 52 wks)")
        fig.update_layout(title=f"{ch}: steady-state weekly new MRR vs weekly spend (diminishing returns)", xaxis_title="weekly spend (USD)", yaxis_title="weekly new MRR (USD)")
        st.plotly_chart(fig, width="stretch")
        st.caption("Beyond the highest spend seen in the data the curve is extrapolation and should not be trusted.")
    with tabs[5]:
        spend_cols = [c for c in scen.columns if c.startswith("spend_")]
        st.dataframe(scen[["scenario", "weekly_budget_usd", *spend_cols, "predicted_weekly_media_mrr", "delta_vs_current", "delta_p05", "delta_p95", "prob_better_than_current"]], width="stretch", hide_index=True)
        ui.download(scen, "mmm_budget_scenarios")
        st.caption("Optimised plans maximise predicted weekly MRR for a FIXED budget with each channel kept within 50-150% of its current level (budget +10%/-20% scenarios widen/narrow the bounds). "
                   "'Probability better' = share of bootstrap draws in which the plan beats the current mix.")
        st.subheader("Try your own allocation")
        params = summ.set_index("channel")
        cols = st.columns(4)
        alloc = []
        for col, m in zip(cols, MEDIA):
            ch = m.replace("spend_", "")
            cur = float(params.loc[ch, "current_weekly_spend_usd"])
            alloc.append(col.slider(f"{ch} $/week", 0.0, float(round(cur * 2.5)), float(round(cur)), step=50.0))
        betas = np.array([float(data.table(A, "mmm_params").set_index("term").loc[m, "coefficient"]) for m in MEDIA])
        dec = np.array([float(params.loc[m.replace("spend_", ""), "decay"]) for m in MEDIA])
        sc = np.array([float(params.loc[m.replace("spend_", ""), "saturation_scale_usd"]) for m in MEDIA])
        cur_alloc = np.array([float(params.loc[m.replace("spend_", ""), "current_weekly_spend_usd"]) for m in MEDIA])
        mine, now = B.response(np.array(alloc), betas, dec, sc), B.response(cur_alloc, betas, dec, sc)
        ui.kpis([("Your weekly budget", ui.fmt_usd(sum(alloc)), None), ("Predicted media MRR / week", ui.fmt_usd(mine), "Steady-state, point estimate"), ("vs current mix", ui.fmt_usd(mine - now), "Positive = better than the last-52-week mix")])
        if any(a > 1.5 * c for a, c in zip(alloc, cur_alloc)):
            st.warning("A channel is above 150% of its current spend - extrapolation risk.")
    with tabs[6]:
        top = summ.sort_values("share_of_revenue", ascending=False).iloc[0]
        opt = scen[scen.scenario == "optimised, same budget"].iloc[0]
        st.markdown(f"""
**Example: how a marketing director could use this**

1. **Where does paid media matter?** In this run the largest estimated contributor is **{top.channel}** (~{top.share_of_revenue:.0%} of weekly new MRR, 90% interval {top.share_p05:.0%}-{top.share_p95:.0%}). Channels whose interval reaches zero should not be defended or cut on MMM evidence alone.
2. **Is there room to scale?** Compare *current spend* with each channel's response curve and marginal return ({', '.join(f"{r.channel}: {r.marginal_weekly_mrr_per_extra_usd:.2f}" for _, r in summ.iterrows())} extra weekly MRR per extra $1/week). Flat curves = saturated.
3. **What if the budget stays the same?** The optimiser shifts {', '.join(f"{c.replace('spend_', '')} {opt[c] - scen.iloc[0][c]:+,.0f}" for c in spend_cols_for(scen))} $/week, predicting {opt.delta_vs_current:+,.0f} weekly MRR ({opt.delta_p05:+,.0f} to {opt.delta_p95:+,.0f}); better than today in {opt.prob_better_than_current:.0%} of bootstrap draws.
4. **Decide, then verify.** Treat the shift as an experiment: move a portion of budget in a staged or geo-split test, measure with a holdout, and feed the result back into the model.
5. **Do not** read contributions as causal proof, extrapolate beyond observed spend, or ignore the diagnostics flagged above.
""")


def spend_cols_for(scen):
    return [c for c in scen.columns if c.startswith("spend_")]
