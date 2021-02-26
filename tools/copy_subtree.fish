#!/usr/bin/fish
vf activate order
cd /var/www/order
find tenants -maxdepth 1 -mindepth 1 -exec basename {} \; | \
    while read tenant
        echo $tenant
        set PYTHONPATH=/var/www/order/tenants/$tenant
        celery -A tenants.$tenant.main call app.network.jobs.copy_subtree
    end
