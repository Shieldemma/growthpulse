-- Grain: one row per lifecycle (CRM) experiment.
select
    cast(experiment_id as {{ growthpulse.t_string() }})   as experiment_id,
    cast(experiment_name as {{ growthpulse.t_string() }}) as experiment_name,
    cast(hypothesis as {{ growthpulse.t_string() }})      as hypothesis,
    cast(start_date as date) as start_date,
    cast(end_date as date)   as end_date,
    cast(program_cost_usd as {{ growthpulse.t_float() }}) as program_cost_usd,
    cast(planned_alpha as {{ growthpulse.t_float() }})    as planned_alpha
from {{ source('growthpulse_raw', 'lifecycle_experiment_catalog') }}
