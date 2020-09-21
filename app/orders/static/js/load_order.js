const g_order_id = window.location.href.slice(-16);
(function() { // Isolating variables

$(document).ready(startup);

function startup() {
    get_order(g_order_id);
}

function get_order(order_id) {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/order/' + order_id,
        success: data => {
            g_dictionaries_loaded
                .then(() => {
                    populate_order(data);
                    $('.wait').hide();
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

function populate_order(order_data) {
    cleanup();
    $('#name').val(order_data.customer);
    $('#address').val(order_data.address);
    $('#phone').val(order_data.phone);
    $('#country').val(order_data.country.id);
    get_shipping_methods(order_data.country.id, 0)
        .then(() => { 
            console.log($('#shipping').val());
            console.log($('#shipping')[0].options);
            $('#shipping').val(order_data.shipping.id);
            console.log($('#shipping').val());
        });
    var current_subcustomer;
    var current_node;
    var item;
    var sorted_order_products = order_data.order_products.sort((a, b) => {
        if (a.subcustomer < b.subcustomer) {
            return -1;
        } else if (a.subcustomer > b.subcustomer) {
            return 1;
        } else {
            return 0;
        }
    })
    for (op in sorted_order_products) {
        if (current_subcustomer != sorted_order_products[op].subcustomer) {
            current_node = add_user(sorted_order_products[op].subcustomer);
            current_subcustomer = sorted_order_products[op].subcustomer;
            // item = 0;
        } else {
            var button = $('input[id^=add_userItem]', current_node).attr('id');
            add_product_row(button);
        }
        var current_row = $('.item-code', current_node).last().closest('tr')[0];

        fill_product_row(current_row, sorted_order_products[op]);
        // item++;
    }
}

})()