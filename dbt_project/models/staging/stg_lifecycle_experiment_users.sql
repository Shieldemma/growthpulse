-- Grain: experiment_id x unit_id (one trial user).
select
    cast(experiment_id as {{ growthpulse.t_string() }})   as experiment_id,
    cast(unit_id as {{ growthpulse.t_string() }})         as unit_id,
    cast(assigned_group as {{ growthpulse.t_string() }})  as assigned_group,
    cast(assignment_date as date)                         as assignment_date,
    cast(device_category as {{ growthpulse.t_string() }}) as device_category,
    cast(plan_id as {{ growthpulse.t_string() }})         as plan_id,
    cast(paid_30d as {{ growthpulse.t_int() }})           as paid_30d,
    cast(active_90d as {{ growthpulse.t_int() }})         as active_90d,
    cast(active_180d as {{ growthpulse.t_int() }})        as active_180d,
    cast(revenue_30d as {{ growthpulse.t_float() }})      as revenue_30d,
    cast(revenue_90d as {{ growthpulse.t_float() }})      as revenue_90d,
    cast(revenue_180d as {{ growthpulse.t_float() }})     as revenue_180d
from {{ source('growthpulse_raw', 'lifecycle_experiment_users') }}
