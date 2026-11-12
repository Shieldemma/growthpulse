# %% [markdown]
# # Explore GrowthPulse results (SYNTHETIC data)
# Run `python scripts/run_pipeline.py` first. Each cell below can be run on its own in VS Code.

# %%
import sys
from pathlib import Path
ROOT = Path.cwd() if (Path.cwd() / "src").exists() else Path.cwd().parent
sys.path.insert(0, str(ROOT / "src"))
import duckdb, pandas as pd
import plotly.express as px
con = duckdb.connect(str(ROOT / "data/processed/growthpulse.duckdb"), read_only=True)

# %% [markdown]
# ## 1. Spend vs new customers per month (all channels, first-touch)

# %%
m = con.sql("""
    select date_trunc('month', metric_date) as month, sum(spend_usd) as spend, sum(new_customers) as customers
    from gp_marts.mart_marketing_performance where attribution_model = 'first_touch' group by 1 order by 1""").df()
fig = px.bar(m, x="month", y="spend", title="Monthly media spend (synthetic)")
fig.show() if "ipykernel" in sys.modules else print(m.tail())

# %% [markdown]
# ## 2. Retention curves by acquisition channel

# %%
r = con.sql("""
    select acquisition_channel, months_since_start,
           sum(customers_retained) * 1.0 / sum(customers_observed) as retention
    from gp_marts.mart_customer_retention group by 1, 2 having sum(customers_observed) >= 30 order by 1, 2""").df()
fig = px.line(r, x="months_since_start", y="retention", color="acquisition_channel", title="Retention by channel (synthetic)")
fig.show() if "ipykernel" in sys.modules else print(r.groupby("acquisition_channel").retention.last())

# %% [markdown]
# ## 3. Experiment results

# %%
print(con.sql("select experiment_id, rate_control, rate_treatment, rel_lift, rel_lift_ci_low, rel_lift_ci_high, p_value from gp_analytics.experiment_results").df())
