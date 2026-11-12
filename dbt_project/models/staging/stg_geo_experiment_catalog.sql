-- Grain: one row per geo experiment.
select
    cast(experiment_id as {{ growthpulse.t_string() }})   as experiment_id,
    cast(experiment_name as {{ growthpulse.t_string() }}) as experiment_name,
    cast(hypothesis as {{ growthpulse.t_string() }})      as hypothesis,
    cast(channel_id as {{ growthpulse.t_string() }})      as channel_id,
    cast(pre_start_date as date)  as pre_start_date,
    cast(test_start_date as date) as test_start_date,
    cast(test_end_date as date)   as test_end_date,
    cast(n_geos as {{ growthpulse.t_int() }}) as n_geos
from {{ source('growthpulse_raw', 'geo_experiment_catalog') }}
