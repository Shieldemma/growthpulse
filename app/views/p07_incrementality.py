import json

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from growthpulse import experiment as E, paths
from lib import data, ui


def render():
    data.require_data()
    ui.header("Incrementality Experiment", "Did the campaign cause extra conversions, or did it take credit for conversions that would have happened anyway?")
    res = data.table(paths.ANALYTICS, "experiment_results")
    if res.empty:
        return ui.empty_state("No experiment results.", "Run the pipeline.")
    st.sidebar.header("Experiment")
    eid = st.sidebar.selectbox("Experiment", res.experiment_id, format_func=lambda x: f"{x} - {res.set_index('experiment_id').loc[x, 'experiment_name']}")
    r = res[res.experiment_id == eid].iloc[0]
    st.caption("These are **simulated** experiments with known true effects - not real company experiments.")
    st.markdown(f"**Hypothesis.** {r.hypothesis}  \n**Design.** Users randomly assigned 50/50 to treatment (eligible for the ads) or control (held out). Outcome: paid conversion within {r.outcome_window_days} days. Test at alpha = {r.alpha}. Primary analysis = intent-to-treat.")
    ui.kpis([("Control rate", ui.fmt_pct(r.rate_control, 2), f"{int(r.conv_control):,} / {int(r.n_control):,}"),
             ("Treatment rate", ui.fmt_pct(r.rate_treatment, 2), f"{int(r.conv_treatment):,} / {int(r.n_treatment):,}"),
             ("Absolute lift", f"{r.abs_lift * 100:+.2f} pp", f"95% CI {r.abs_lift_ci_low * 100:+.2f} to {r.abs_lift_ci_high * 100:+.2f} pp"),
             ("Relative lift", ui.fmt_pct(r.rel_lift, 1), f"95% CI {ui.fmt_pct(r.rel_lift_ci_low, 1)} to {ui.fmt_pct(r.rel_lift_ci_high, 1)}"),
             ("p-value", f"{r.p_value:.4f}", "Two-sided two-proportion z-test")])
    (st.success if r.significant and r.srm_ok else st.warning)(r.verdict)
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure(go.Scatter(x=[r.abs_lift * 100], y=["Absolute lift (pp)"], mode="markers", marker=dict(size=12),
                                   error_x=dict(type="data", symmetric=False, array=[(r.abs_lift_ci_high - r.abs_lift) * 100], arrayminus=[(r.abs_lift - r.abs_lift_ci_low) * 100])))
        fig.add_vline(x=0, line_dash="dot")
        fig.update_layout(title="Lift with 95% confidence interval", xaxis_title="percentage points", height=260, margin=dict(t=50))
        st.plotly_chart(fig, width="stretch")
        st.caption("If the interval spans zero, the data are compatible with no effect. A wide interval means the test could not rule out large effects either way.")
    with c2:
        roas = pd.DataFrame({"measure": ["Attributed ROAS (credits all exposed converters)", "Incremental ROAS (randomised, first payment)"], "value": [r.attributed_roas, r.incremental_roas]})
        st.plotly_chart(px.bar(roas, x="measure", y="value", title="What attribution claims vs what the experiment shows").update_layout(height=300, xaxis_title=""), width="stretch")
    st.subheader("Business impact (explicit assumptions)")
    st.markdown(f"- Incremental conversions in treatment: **{r.incremental_conversions:,.0f}** (= absolute ITT lift x treated users)  \n"
                f"- Incremental first-payment revenue: **{ui.fmt_usd(r.incremental_revenue_usd)}** vs test spend **{ui.fmt_usd(r.test_spend_usd)}** -> incremental ROAS **{ui.fmt_num(r.incremental_roas, 2)}**  \n"
                f"- Incremental cost per acquisition: **{ui.fmt_usd(r.incremental_cpa)}** vs attributed CPA **{ui.fmt_usd(r.attributed_cpa)}**  \n"
                "- Assumes the lift observed in this window persists proportionally, ignores later renewals (lifetime value would raise the return), and treats the sample as representative.")
    st.subheader("Practical vs statistical significance")
    st.markdown(f"Statistical significance says whether the effect is distinguishable from zero (here p = {r.p_value:.3f}). Practical significance asks whether it is **big enough to matter economically**: "
                f"incremental ROAS of {ui.fmt_num(r.incremental_roas, 2)} on first payments must be compared with how long customers stay (see LTV). A tiny but significant lift can be unprofitable; a large but non-significant one may just be an underpowered test.")
    st.subheader("Power and sample size")
    ui.kpis([("Minimum detectable effect", ui.fmt_pct(r.mde_relative, 0), "Smallest relative lift detectable with 80% power at this sample size"),
             ("Power at observed lift", ui.fmt_pct(r.power_at_observed_lift, 0), "Probability of detecting a lift of the observed size"),
             ("n per arm to detect observed lift", ui.fmt_num(r.required_n_per_arm_for_observed_lift), "80% power, alpha 0.05"),
             ("n per arm used", ui.fmt_num(min(r.n_treatment, r.n_control)), None)])
    with st.expander("Power calculator (plan your next test)"):
        c = st.columns(4)
        base = c[0].number_input("Baseline conversion rate", 0.001, 0.5, float(max(r.rate_control, 0.001)), 0.001, format="%.3f")
        mde = c[1].slider("Relative lift to detect", 0.02, 1.0, 0.15, 0.01)
        alpha = c[2].selectbox("Alpha", [0.01, 0.05, 0.10], index=1)
        pw = c[3].selectbox("Power", [0.7, 0.8, 0.9], index=1)
        n = E.required_sample_size_per_arm(base, mde, alpha, pw)
        st.metric("Required users per arm", f"{n:,}")
    st.subheader("Randomisation and contamination checks")
    b = data.table(paths.ANALYTICS, "experiment_balance", f"where experiment_id = '{eid}'")
    cc = data.table(paths.ANALYTICS, "experiment_contamination", f"where experiment_id = '{eid}'").iloc[0]
    k1, k2, k3 = st.columns(3)
    k1.metric("Sample-ratio check (p)", f"{r.srm_p_value:.3f}", "OK" if r.srm_ok else "MISMATCH", delta_color="normal" if r.srm_ok else "inverse")
    k2.metric("Treatment users never exposed", ui.fmt_pct(cc.treatment_not_exposed_share, 1))
    k3.metric("Control users exposed (contamination)", ui.fmt_pct(cc.control_exposed_share, 1))
    st.dataframe(b[["covariate", "smd", "p_value", "balanced"]], width="stretch", hide_index=True)
    st.caption(f"Effect on the exposed (CACE/Wald, needs the assumption that assignment works only through exposure): relative lift about {ui.fmt_pct(r.cace_rel_lift, 1)}. ITT is the headline because it relies only on randomisation.")
    gt = data.table(paths.ANALYTICS, "experiment_ground_truth", f"where experiment_id = '{eid}'")
    if not gt.empty:
        with st.expander("Synthetic ground truth (only possible because the data are simulated)"):
            g = gt.iloc[0]
            st.markdown(f"True relative lift among exposed: **{g.true_relative_lift_among_exposed:.0%}**; expected ITT relative lift after non-compliance: **{g.expected_itt_relative_lift:.1%}**. "
                        f"Estimated ITT: **{r.rel_lift:.1%}** (95% CI {r.rel_lift_ci_low:.1%} to {r.rel_lift_ci_high:.1%}) - the interval {'contains' if r.rel_lift_ci_low <= g.expected_itt_relative_lift <= r.rel_lift_ci_high else 'MISSES'} the truth.")
    st.subheader("How this would change for a real campaign")
    st.markdown("""
- **Pre-register** the hypothesis, primary metric, window, alpha and minimum effect of interest *before* launch; compute sample size from the baseline rate.
- Randomise at the right unit (user, household or **geo** when cookies/IDs are unreliable) and use **ghost ads / PSA control** so control users are eligible for the auction but are not shown the ad.
- Log exposure to measure compliance and contamination; keep the primary analysis intent-to-treat.
- Run for full weekly cycles, do not peek and stop early, and avoid overlapping campaigns that contaminate control.
- Consider geo experiments or synthetic control when user-level holdouts are infeasible, and calibrate the MMM with the experiment results.
""")
