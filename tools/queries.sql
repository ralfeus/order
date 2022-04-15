set @@cte_max_recursion_depth =10000;
-- Update Cargo-Booster
delete from shipping_rates where shipping_method_id = 8;
insert into shipping_rates (destination, weight, rate, shipping_method_id) 
with recursive cte (destination, weight, rate, shipping_method_id) as (
    select 'ru', 500, 8000, 8
    union
    select 'ru', weight + 500, rate + 8000, 8 from cte where weight < 1000000
) select * from cte;

-- Update Cargo via Kazakhstan
delete from shipping_rates where shipping_method_id = 9;
insert into shipping_rates (destination, weight, rate, shipping_method_id) 
with recursive cte (destination, weight, rate, shipping_method_id) as (
    select 'ru', 5000, 112500, 9
    union
    select 'ru', weight + 500, rate + 11300, 9 from cte where weight < 300000
) select * from cte;

-- Update Cargo Noni
delete from shipping_rates where shipping_method_id = 11;
insert into shipping_rates (destination, weight, rate, shipping_method_id) 
with recursive cte (destination, weight, rate, shipping_method_id) as (
    select 'ru', 200, 1800, 11
    union
    select 'ru', weight + 200, rate + 1800, 11 from cte where weight < 1000000
) select * from cte;

-- Update Cargo via Russia
set @@cte_max_recursion_depth =10000;
delete from shipping_rates where shipping_method_id = 3;
insert into shipping_rates (destination, weight, rate, shipping_method_id) 
with recursive cte (destination, weight, rate, shipping_method_id) as (
    select 'ru', 5000, 110000, 3
    union
    select 'ru', weight + 100, rate + 2200, 3 from cte where weight < 300000
) select * from cte;
