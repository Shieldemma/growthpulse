-- Grain: one row per experiment.
select
    cast(experiment_id as {{ growthpulse.t_string() }})         as experiment_id,
    cast(experiment_name as {{ growthpulse.t_string() }})       as experiment_name,
    cast(hypothesis as {{ growthpulse.t_string() }})            as hypothesis,
    cast(channel_id as {{ growthpulse.t_string() }})            as channel_id,
    cast(start_date as date)              as start_date,
    cast(end_date as date)                as end_date,
    cast(outcome_window_days as {{ growthpulse.t_int() }})      as outcome_window_days,
    cast(planned_alpha as {{ growthpulse.t_float() }})        as planned_alpha,
    cast(test_spend_usd as {{ growthpulse.t_float() }})       as test_spend_usd,
    cast(attributed_revenue_usd as {{ growthpulse.t_float() }}) as attributed_revenue_usd
from {{ source('growthpulse_raw', 'experiment_catalog') }}
