-- A visitor cannot reach a later funnel step without the earlier one.
select * from {{ ref('mart_growth_funnel') }}
where pricing_viewers > visitors or signup_starters > pricing_viewers or signups > signup_starters
   or trials > signups or paying_customers > trials
