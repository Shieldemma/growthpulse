-- Geo grain must be unique and each geo must keep ONE assignment for the whole experiment (no switching groups).
select geo_id, count(*) as n_rows, count(distinct assigned_group) as n_groups, count(distinct activity_date) as n_days
from {{ ref('stg_geo_daily_outcomes') }}
group by geo_id
having count(*) <> count(distinct activity_date) or count(distinct assigned_group) > 1
