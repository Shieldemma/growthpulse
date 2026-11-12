-- Every customer must receive exactly 1.0 credit under each attribution model.
select c.customer_id, m.attribution_model, coalesce(sum(a.credit), 0.0) as total_credit
from {{ ref('int_customer_acquisition') }} c
cross join (select distinct attribution_model from {{ ref('int_attribution_credit') }}) m
left join {{ ref('int_attribution_credit') }} a on a.customer_id = c.customer_id and a.attribution_model = m.attribution_model
group by c.customer_id, m.attribution_model
having abs(coalesce(sum(a.credit), 0.0) - 1.0) > 0.000001
