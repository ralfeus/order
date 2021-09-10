var g_country_destination_name;
var g_shipping_rates

$.fn.dataTable.ext.buttons.status = {
    action: function(_e, dt, _node, _config) {
        set_status(dt.rows({selected: true}), this.text());
    }
};

function g_country_destination_name ()
    

