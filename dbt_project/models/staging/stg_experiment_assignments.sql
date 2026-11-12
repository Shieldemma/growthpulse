-- Grain: one row per experimental unit per experiment.
select
    cast(experiment_id as {{ growthpulse.t_string() }})   as experiment_id,
    cast(unit_id as {{ growthpulse.t_string() }})         as unit_id,
    cast(assigned_group as {{ growthpulse.t_string() }})  as assigned_group,
    cast(assignment_date as date)   as assignment_date,
    cast(device_category as {{ growthpulse.t_string() }}) as device_category,
    cast(prior_sessions as {{ growthpulse.t_int() }})     as prior_sessions,
    cast(was_exposed as {{ growthpulse.t_int() }})        as was_exposed,
    cast(converted as {{ growthpulse.t_int() }})          as converted,
    cast(revenue_usd as {{ growthpulse.t_float() }})    as revenue_usd
from {{ source('growthpulse_raw', 'experiment_assignments') }}
