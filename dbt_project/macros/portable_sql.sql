{#- Small cross-database helpers so the SAME model SQL runs on DuckDB (local) and BigQuery (cloud). -#}

{% macro safe_divide(numerator, denominator) -%}
  (({{ numerator }}) * 1.0 / nullif(({{ denominator }}), 0))
{%- endmacro %}

{# ---- first day of the (Monday-based) week ---- #}
{% macro week_start(date_expr) -%}
  {{ return(adapter.dispatch('week_start', 'growthpulse')(date_expr)) }}
{%- endmacro %}
{% macro default__week_start(date_expr) -%}cast(date_trunc('week', {{ date_expr }}) as date){%- endmacro %}
{% macro bigquery__week_start(date_expr) -%}date_trunc({{ date_expr }}, week(monday)){%- endmacro %}

{% macro month_start(date_expr) -%}
  {{ return(adapter.dispatch('month_start', 'growthpulse')(date_expr)) }}
{%- endmacro %}
{% macro default__month_start(date_expr) -%}cast(date_trunc('month', {{ date_expr }}) as date){%- endmacro %}
{% macro bigquery__month_start(date_expr) -%}date_trunc({{ date_expr }}, month){%- endmacro %}

{# ---- date arithmetic ---- #}
{% macro add_days(date_expr, n) -%}
  {{ return(adapter.dispatch('add_days', 'growthpulse')(date_expr, n)) }}
{%- endmacro %}
{% macro default__add_days(date_expr, n) -%}cast(({{ date_expr }}) + cast(({{ n }}) as integer) as date){%- endmacro %}
{% macro bigquery__add_days(date_expr, n) -%}date_add({{ date_expr }}, interval cast(({{ n }}) as int64) day){%- endmacro %}

{% macro add_months(date_expr, n) -%}
  {{ return(adapter.dispatch('add_months', 'growthpulse')(date_expr, n)) }}
{%- endmacro %}
{% macro default__add_months(date_expr, n) -%}cast(({{ date_expr }}) + to_months(cast(({{ n }}) as integer)) as date){%- endmacro %}
{% macro bigquery__add_months(date_expr, n) -%}date_add({{ date_expr }}, interval cast(({{ n }}) as int64) month){%- endmacro %}

{# days_between(a, b) = b - a in whole days #}
{% macro days_between(start_date, end_date) -%}
  {{ return(adapter.dispatch('days_between', 'growthpulse')(start_date, end_date)) }}
{%- endmacro %}
{% macro default__days_between(start_date, end_date) -%}date_diff('day', {{ start_date }}, {{ end_date }}){%- endmacro %}
{% macro bigquery__days_between(start_date, end_date) -%}date_diff({{ end_date }}, {{ start_date }}, day){%- endmacro %}

{% macro data_end_date() -%}cast('{{ var("data_end_date") }}' as date){%- endmacro %}

{# ---- portable type names (DuckDB vs BigQuery) ---- #}
{% macro t_string() -%}{{ return(adapter.dispatch('t_string', 'growthpulse')()) }}{%- endmacro %}
{% macro default__t_string() -%}varchar{%- endmacro %}
{% macro bigquery__t_string() -%}string{%- endmacro %}

{% macro t_float() -%}{{ return(adapter.dispatch('t_float', 'growthpulse')()) }}{%- endmacro %}
{% macro default__t_float() -%}double{%- endmacro %}
{% macro bigquery__t_float() -%}float64{%- endmacro %}

{% macro t_int() -%}{{ return(adapter.dispatch('t_int', 'growthpulse')()) }}{%- endmacro %}
{% macro default__t_int() -%}integer{%- endmacro %}
{% macro bigquery__t_int() -%}int64{%- endmacro %}

{% macro t_bigint() -%}{{ return(adapter.dispatch('t_bigint', 'growthpulse')()) }}{%- endmacro %}
{% macro default__t_bigint() -%}bigint{%- endmacro %}
{% macro bigquery__t_bigint() -%}int64{%- endmacro %}

{# 'YYYY-MM' label for a date (sortable text used by BI tools) #}
{% macro year_month(date_expr) -%}
  {{ return(adapter.dispatch('year_month', 'growthpulse')(date_expr)) }}
{%- endmacro %}
{% macro default__year_month(date_expr) -%}strftime({{ date_expr }}, '%Y-%m'){%- endmacro %}
{% macro bigquery__year_month(date_expr) -%}format_date('%Y-%m', {{ date_expr }}){%- endmacro %}
