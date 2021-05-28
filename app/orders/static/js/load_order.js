var g_order_id ;
(function() { // Isolating variables

$(document).ready(startup);

function startup() {
    g_order_id = $('#order_id').val();
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
    modals_off();
    cleanup();
    $('#name').val(order_data.customer_name);
    $('#comment').val(order_data.comment);
    $('#address').val(order_data.address);
    $('#phone').val(order_data.phone);
    $('#zip').val(order_data.zip);
    $('#country').val(order_data.country.id);
    order_data.attached_orders.forEach(ao => {
        $('#attached_orders')
            .append(new Option(ao.id, ao.id, false, true)).trigger('change');
    });

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
            add_product(current_row, order_products[op])
            // await update_product(current_row, order_products[op])
        }
        await update_subcustomer_local_shipping(current_node);
    }
    update_shipping_methods(order_data.country.id, g_total_weight + g_box_weight)
    .then(() => { 
        $('#shipping').val(order_data.shipping.id);     
        shipping_changed();
        modals_on();
    });
}

function add_product(product_row, product) {
    if (product.product_id) {
        $('.item-code', product_row).val(product.product_id);
    }
    if (!isNaN(product.quantity)) {
        $('.item-quantity', product_row).val(product.quantity);
    }
    if (product.available) {
        $('.item-code', product_row).attr('title', '');
        $('.item-code', product_row).addClass('is-valid');
        $('.item-code', product_row).removeClass('is-invalid');
    } else {
        $('.item-code', product_row).attr('data-toggle', 'tooltip');
        $('.item-code', product_row).attr('data-delay', '{show:5000, hide: 3000}');
        $('.item-code', product_row).attr('title', 'The product is not available');
        $('.item-code', product_row).addClass('is-invalid');
        $('.item-code', product_row).removeClass('is-valid');
    }
    var color = product.color ? product.color : '#000000';
    $('.item-name', product_row).html(
        "<font color=\"" + color + "\">" +
        (product.name_english == null
            ? product.name
            : product.name_english + " | " + product.name_russian) +
        "</font>");
    $('.item-price', product_row).html(product.price);
    $('.item-points', product_row).html(product.points);
    g_cart[product_row.id] = product;
    update_item_subtotal(product_row)
}

function update_item_subtotal(item) {
    if (g_cart[item.id]) {
        g_cart[item.id].user = '';
        g_cart[item.id].quantity = parseInt($('.item-quantity', item).val());
        g_cart[item.id].costKRW = g_cart[item.id].price * g_cart[item.id].quantity;
        $('td.cost-krw', item).html(g_cart[item.id].costKRW);
        $('td.total-item-weight', item).html(g_cart[item.id].weight * g_cart[item.id].quantity);
        $('td.total-points', item).html(g_cart[item.id].points * g_cart[item.id].quantity);
    } else {
        $('.cost-krw', item).html('');
        $('.total-item-weight', item).html('');
        $('.total-points', item).html('');
    }
}
})()