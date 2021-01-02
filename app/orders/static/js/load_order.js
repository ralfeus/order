const g_order_id = window.location.href.slice(-16);
(function() { // Isolating variables

$(document).ready(startup);

function startup() {
    get_order(g_order_id);
}

function get_order(order_id) {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/order/' + order_id + '?details=1',
        success: data => {
            g_dictionaries_loaded
                .then(() => {
                    populate_order(data)
                    .then(() => {
                        $('.wait').hide();
                    });
                });
        },
        error: xhr => {
            $('.wait').hide();
            $('.modal-title').text('Something went wrong...');
            $('.modal-body').text(xhr.responseText);
            $('.modal').modal();
        }
    })
}

async function populate_order(order_data) {
    cleanup();
    $('#name').val(order_data.customer_name);
    $('#address').val(order_data.address);
    $('#phone').val(order_data.phone);
    $('#zip').val(order_data.zip);
    $('#country').val(order_data.country.id);
    order_data.attached_orders.forEach(ao => {
        $('#attached_orders')
            .append(new Option(ao.id, ao.id, false, true)).trigger('change');
    });
    get_shipping_methods(order_data.country.id, 0)
    .then(() => { $('#shipping').val(order_data.shipping.id); });

    var current_node;
    for (i in order_data.suborders) {
        var suborder = order_data.suborders[i];
        var current_node = add_user(suborder.subcustomer);
        $('.subcustomer-seq-num', current_node).val(suborder.seq_num);
        $('.subcustomer-buyout-date', current_node).val(suborder.buyout_date);
        var order_products = suborder.order_products;
        for (op in order_products) {
            if (op > 0) {
                var button = $('input[id^=add_userItem]', current_node).attr('id');
                add_product_row(button);
            }
            var current_row = $('.item-code', current_node).last().closest('tr')[0];

            await fill_product_row(current_row, order_products[op])
        }
    }
    shipping_changed();
}

})()