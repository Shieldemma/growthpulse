{# Custom generic tests (kept local so the project needs no external dbt packages). #}

{% test non_negative(model, column_name) %}
select * from {{ model }} where {{ column_name }} < 0
{% endtest %}

{% test expression_is_true(model, expression) %}
select * from {{ model }} where not ({{ expression }})
{% endtest %}

{# Fails when column is outside [lo, hi] (NULLs ignored - add not_null separately). #}
{% test between_values(model, column_name, lo, hi) %}
select * from {{ model }} where {{ column_name }} < {{ lo }} or {{ column_name }} > {{ hi }}
{% endtest %}
