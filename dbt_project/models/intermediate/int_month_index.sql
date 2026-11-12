-- Grain: one row per month_index (0..max_month_index). A tiny number spine used by retention logic.
{% for i in range(0, var('max_month_index') + 1) %}
select {{ i }} as month_index{% if not loop.last %} union all{% endif %}
{% endfor %}
