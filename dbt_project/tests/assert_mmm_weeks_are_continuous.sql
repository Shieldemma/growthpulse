-- The MMM needs an unbroken weekly series: number of weeks must equal the calendar span.
select count(*) as n_weeks, min(week_start) as first_week, max(week_start) as last_week
from {{ ref('mart_mmm_weekly') }}
having count(*) <> {{ growthpulse.days_between('min(week_start)', 'max(week_start)') }} / 7 + 1
