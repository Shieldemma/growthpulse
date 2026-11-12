-- BI dimension. Grain: one row per calendar day that appears in the spend data (unique date_day).
select
    d as date_day,
    {{ growthpulse.week_start('d') }}  as week_start,
    {{ growthpulse.month_start('d') }} as month_start,
    {{ growthpulse.year_month('d') }}  as year_month,
    extract(year from d)    as year,
    extract(quarter from d) as quarter
from (select distinct spend_date as d from {{ ref('fct_marketing_spend') }}) days
