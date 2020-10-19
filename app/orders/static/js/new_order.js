const g_dictionaries_loaded = $.Deferred();
const box_weights = {
    30000: 2200,
    20000: 1900,
    15000: 1400,
    10000: 1000,
    5000: 500,
    2000: 250
};
const FREE_LOCAL_SHIPPING_THRESHOLD = 30000;
const LOCAL_SHIPPING_COST = 2500;

var g_selected_shipping_method;
var g_products;
var g_cart = {};

var itemsCount = {};
var currencyRates = {};
var users = 1;

var subtotal_krw = 0;
var totalWeight = 0;

var subcustomerTemplate;
var itemTemplate;

$(document).ready(function() {
    itemTemplate = $('#userItems0_0')[0].outerHTML;
    subcustomerTemplate = $('.subcustomer-card')[0].outerHTML;

    $(document).on("click", "[id^=add_userItems]", (event) => add_product_row(event.target.id));
    $('#add_user').on('click', add_subcustomer);
    $('#submit').on('click', submit_order)
    $('.subcustomer-buyout-date').datepicker({
	format: 'dd.mm.yyyy',
	todayHighlight: true,
        autoclose: true
    });

    load_dictionaries();
    g_dictionaries_loaded
        .then(() => product_code_autocomplete($('.item-code')));
    product_quantity_change($('.item-quantity'));
});

function add_product_row(idString) {
    var id = idString.substring(13)
    if (isNaN(itemsCount[id])) {
        itemsCount[id] = 1;
    } 
    var html = itemTemplate
        .replace(/userItems0_0/g, 'userItems' + id + '_' + itemsCount[id])
    $('#userItemsList' + id).append(html);
    product_code_autocomplete($('.item-code'));
    product_quantity_change($('.item-quantity'));
    itemsCount[id]++; 
    window.scrollTo(0,document.body.scrollHeight);
}

function add_subcustomer() {
    var html = subcustomerTemplate
        .replace(/userItems([A-Za-z]*)0/g, 'userItems$1' + users)
        .replace(/identity0/g, "identity" + users)
        .replace(/(\w)\[0\]/g, '$1[' + users + ']');
    var node = $(html)
    $('div#accordion').append(node);
    $('.subcustomer-buyout-date').datepicker({
	format: 'dd.mm.yyyy',
	todayHighlight: true,
        autoclose: true
    });
    product_code_autocomplete($('.item-code'));
    product_quantity_change($('.item-quantity'));
    users++;
    window.scrollTo(0,document.body.scrollHeight);
    return node;
}

function clear_form() {
    g_cart = {};
    itemsCount = {};
    users = 1;
    subtotal_krw = 0;
    totalWeight = 0;

    $('.subcustomer-card').remove();
    add_subcustomer();
    //$('div#accordion').append(subcustomerTemplate);
    //product_code_autocomplete($('.item-code'));
    //product_quantity_change($('.item-quantity'));
}

function country_changed() {
    update_all_totals();
}

function delete_subcustomer(target) {
    var userId = $(target).parent().attr('id').substr(15);
        for (product in g_cart) {
            if (product.match(new RegExp('userItems' + userId + '_\\d+'))) {
                delete g_cart[product];
            }
        }
        $(target).parent().parent().remove();
        update_all_totals();
}

function delete_product(target) {
    var userItemId = target.id.substr(4);
    if(!userItemId.match(/userItems\d+_0/)) {
        delete g_cart[userItemId];
        update_all_totals();
        $(target).parent().parent().remove();
    }
}

function fill_product_row(product_row, product) {
    if (product.product_id) {
        $('.item-code', product_row).val(product.product_id);
    }
    if (!isNaN(product.quantity)) {
        $('.item-quantity', product_row).val(product.quantity);
    }
    $('.item-name', product_row).html(
        product.name_english == null
            ? product.name
            : product.name_english + " | " + product.name_russian);
    $('.item-price', product_row).html(product.price);
    $('.item-points', product_row).html(product.points);
    g_cart[product_row.id] = product;
    update_item_subtotal($('.item-quantity', product_row));
}

function get_countries() {
    var promise = $.Deferred();
    $.ajax({
        url: '/api/v1/country',
        success: function(data) {
            $('#country').html(data.map(c => '<option value="' + c.id + '">' + c.name + '</option>'))
            get_shipping_methods($('#country').val(), 0);
            promise.resolve();
        }
    });
    return promise;
}

function get_currencies() {
    var promise = $.Deferred();
    $.ajax({
        url: '/api/v1/currency',
        success: function(data, _status, _xhr) {
            for (var currency in data) {
                currencyRates[data[currency].code] = data[currency].rate;
            }
            promise.resolve();
        }
    });
    return promise;
}

function get_products() {
    var promise = $.Deferred()
    $.ajax({
        url: '/api/v1/product',
        success: function(data) {
            if (data) {
                g_products = data.map(product => ({
                    value: product.id,
                    label: product.name_english == null
                                ? product.name
                                : product.name_english + " | " + product.name_russian,
                    price: product.price,
                    points: product.points,
                    separate_shipping: product.separate_shipping,
                    weight: product.weight
                }));
            }
            promise.resolve();
        }
    })
    return promise;
}

/**
 * Gets shipping cost for chosen country and weight
 * @param {number} totalWeight - total parcel weight
 */
function get_shipping_cost(shipping_method, weight) {
    if (weight == 0) {
        update_all_grand_totals(0, 0);
    } else {
        update_all_grand_totals(shipping_rates[shipping_method], weight);
    }
}

function get_shipping_methods(country, weight) {
    var promise = $.Deferred()
    if ($('#shipping').val()) {
        g_selected_shipping_method = $('#shipping').val();
    }
    $('#shipping').html('');
    $.ajax({
        url: '/api/v1/shipping/' + country + '/' + weight,
        success: (data, _status, xhr) => {
            $('#shipping').html(data.map(e => '<option value="' + e.id + '">' + e.name + '</option>'));
            if ($('#shipping option').toArray().map(i => i.value).includes(g_selected_shipping_method)) {
                $('#shipping').val(g_selected_shipping_method);
            }
            // console.log("Shipping methods are set:", $('#shipping').html());
            // console.log(xhr);
            $.ajax({
                url: '/api/v1/shipping/rate/' + country + '/' + weight,
                success: data => {
                    shipping_rates = data;
                    get_shipping_cost($('#shipping').val(), weight);
                },
                error: xhr => {
                    if (xhr.status == 409) {
                        // if input params are wrong we set shipping method to 
                        // "No shipping"
                        $('#shipping').val(NO_SHIPPING_ID);
                        get_shipping_cost(NO_SHIPPING_ID, weight);
                    } else {
                        modal('Something went wrong...', xhr.responseText);
                    }
                }
            });
            promise.resolve();
        },
        error: (xhr) => {
            $('.modal-body').text(xhr.responseText);
            $('.modal').modal();
            promise.resolve();
        }
    });
    return promise;
}

function product_code_autocomplete(target) {
    target.autocomplete({
        source: (query, response) => {
            var result = g_products.filter(product =>
                product.value.includes(query.term)
                || product.label.includes(query.term)
            );
            response(result);
        },
        minLength: 2
    });
    target.on('change', () => get_product(event.target));
}

function get_product(line_input) {
    var promise = $.Deferred()
    var product_line = $(line_input).closest('tr')[0];
    if (line_input.value) {
        $.ajax({
            url: '/api/v1/product/' + line_input.value,
            success: data => fill_product_row(product_line, data[0]),
            error: (data) => {
                $('.modal-body').text(data.responseText);
                $('#modal').modal();
            },
            complete: () => { promise.resolve(); }
        });
    } else {
        $('.item-name', product_line).html('');
        $('.item-price', product_line).html('');
        $('.item-points', product_line).html('');
        delete g_cart[product_line.id];
        update_item_subtotal($('.item-quantity', product_line));
        promise.resolve();
    }
    return promise;
}

function load_dictionaries() {
    var dict_left = 3;
    get_countries()
        .then(() => { if (!(--dict_left)) g_dictionaries_loaded.resolve(); });
    get_currencies()
        .then(() => { if (!(--dict_left)) g_dictionaries_loaded.resolve(); });    
    get_products()
        .then(() => { if (!(--dict_left)) g_dictionaries_loaded.resolve(); });
}

function product_quantity_change(target) {
    target.on('change', function() { update_item_subtotal($(this)); });
}

function set_total_weight(total_weight) {
    totalWeight = total_weight;
    get_shipping_methods($('#country').val(), total_weight);
}

function shipping_changed() {
    get_shipping_cost($('#shipping').val(), totalWeight);
}

function submit_order() {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/order' + (typeof g_order_id !== 'undefined' ? '/' + g_order_id : ''),
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            name: $('#name').val(),
            address: $('#address').val(),
            country: $('#country').val(),
            shipping: $('#shipping').val(),
            phone: $('#phone').val(),
            comment: $('#comment').val(),
            suborders: $('div.subcustomer-card').toArray().map(user => ({
                subcustomer: $('.subcustomer-identity', user).val(),
	        buyout_date: $('.subcustomer-buyout-date', user).val(),
                items: $('.item', user).toArray().map(item => ({
                    item_code: $('.item-code', item).val(),
                    quantity: $('.item-quantity', item).val()
                }))
            }))
        }),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data, _status, _xhr) {
            if (data.status === 'success') {
                modal('Success!', "The request is posted. The request ID is " + data.order_id);
                clear_form();
            } else if (data.status === 'updated') {
                $('.modal-title').text('Order update');
                $('.modal-body').text("The request is updated. The request ID is " + data.order_id);
                $('.modal').modal();
            } else if (data.status === 'warning') {
               modal('Almost good...',
                    "The request is posted. The request ID is " + data.order_id +
                    "\nDuring request creation following issues have occurred:\n" +
                    data.message.join("\n"));
            } else if (data.status === 'error') {
                if (data.message) {
                    modal('Something went wrong...', data.message);
                } else {
                    modal('Failure', "Unknown error has occurred. Contact administrator");
                }
            }
        },
        error: xhr => {
            var message;
            if (xhr.status == 500) {
                message = "Unknown error has occurred. Contact administrator"
            } else {
                message = xhr.responseText;
            }
            modal('Failure!', message);
        }
    });
}

/**
 * Updates all grand totals (subtotals + shipping) and items totals 
 * @param {number} shippingCost - shipping cost for chosen country and weight
 * @param {number} totalWeight - total weight of the order
 */
function update_all_grand_totals(shippingCost, totalWeight) {
    update_shipping_cost(shippingCost, totalWeight)
    update_grand_totals();
    update_item_total();
    update_subcustomer_totals();
}

/**
 * Updates all totals (item, subcustomer, grand total)
 */
function update_all_totals() {
    update_grand_subtotal();
}

/**
 * Updates grand totals of the cart
 */
function update_grand_totals() {
    $('#totalGrandTotalKRW').html(round_up(
        parseFloat($('#totalItemsCostKRW').html()) + parseFloat($('#totalShippingCostKRW').html()), 2));
    $('#totalGrandTotalRUR').html(round_up(
        parseFloat($('#totalItemsCostRUR').html()) + parseFloat($('#totalShippingCostRUR').html()), 2));
    $('#totalGrandTotalUSD').html(round_up(
        parseFloat($('#totalItemsCostUSD').html()) + parseFloat($('#totalShippingCostUSD').html()), 2));
}

function update_item_subtotal(sender) {
    var itemObject = sender.parent().parent(); // tr
    var product_id = itemObject.attr('id');
    if (g_cart[product_id]) {
        g_cart[product_id].user = '';
        g_cart[product_id].quantity = sender.val();
        g_cart[product_id].costKRW = g_cart[product_id].price * g_cart[product_id].quantity;
        $('td:nth-child(5)', itemObject).html(g_cart[product_id].costKRW);
        $('td:nth-child(6)', itemObject).html(g_cart[product_id].weight * g_cart[product_id].quantity);
        $('td:nth-child(12)', itemObject).html(g_cart[product_id].points * g_cart[product_id].quantity);
    } else {
        $('.cost-krw', itemObject).html('');
        $('.total-weight', itemObject).html('');
        $('.total-points', itemObject).html('');
    }

    update_subcustomer_local_shipping(sender);
    update_all_totals();
}

function update_item_total() {
    $('.total-krw').each(function() {
        if (g_cart[$(this).parent().attr('id')]) {
            $(this).html(g_cart[$(this).parent().attr('id')].totalKRW);
        } else {
            $(this).html('');
        }
    });
    $('.total-rur').each(function() {
        if (g_cart[$(this).parent().attr('id')]) {
            $(this).html(round_up(g_cart[$(this).parent().attr('id')].totalKRW * currencyRates.RUR, 2));
        } else {
            $(this).html('');
        }
    });
    $('.total-usd').each(function() {
        if (g_cart[$(this).parent().attr('id')]) {
            $(this).html(round_up(g_cart[$(this).parent().attr('id')].totalKRW * currencyRates.USD, 2));
        } else {
            $(this).html('');
        }
    });
}

/**
 * Updates shipping cost in total and distribute one for each ordered item proportionally
 * @param {number} cost - total shipping cost
 * @param {number} totalWeight - total cart weight
 */
function update_shipping_cost(cost, totalWeight) {
    $('#totalShippingCostKRW').html(cost);
    $('#totalShippingCostRUR').html(round_up(cost * currencyRates.RUR, 2));
    $('#totalShippingCostUSD').html(round_up(cost * currencyRates.USD, 2));
    var product_weight = totalWeight - parseInt($('#box-weight').text())

    // Distribute shipping cost among items
    for (product in g_cart) {
        g_cart[product].shippingCostKRW = 
            round_up(cost / product_weight * g_cart[product].weight * g_cart[product].quantity, 0);
        g_cart[product].totalKRW = g_cart[product].costKRW + g_cart[product].shippingCostKRW;
    }
    $('.shipping-cost-krw').each(function() {
        if (g_cart[$(this).parent().attr('id')]) {
            $(this).html(g_cart[$(this).parent().attr('id')].shippingCostKRW);
        } else {
            $(this).html('');
        }
    });
}

function update_subcustomer_local_shipping(node) {
    var subcustomer_card = $(node).closest('.subcustomer-card');
    var subcustomer_total = $('.subcustomer-total', subcustomer_card)[0];
    var userId = parseInt(subcustomer_total.id.substr(14));
    var userProducts = Object.entries(g_cart)
        .filter(product => product[0].startsWith('userItems' + userId))
        .map(product => product[1]);
    var total_local_package_amount = userProducts
        .filter(product => !product.separate_shipping)
        .reduce((acc, product) => acc + product.price * product.quantity, 0);
    var local_shipping = 0;
    if (total_local_package_amount < FREE_LOCAL_SHIPPING_THRESHOLD) {
        $('.local-shipping', $(subcustomer_total)).html(
            "(Local shipping: " + LOCAL_SHIPPING_COST + ')');
        local_shipping = LOCAL_SHIPPING_COST;
    } else {
        $('.local-shipping', $(subcustomer_total)).html("");
        local_shipping = 0;
}}

/**
 * Update subtotal for single customer
 * @param {jQuery} target - div#userItems*
 */
function update_subcustomer_totals() { 
    $('.subcustomer-total').each(function() {
        var userId = parseInt(this.id.substr(14));
        var userProducts = Object.entries(g_cart)
            .filter(product => product[0].startsWith('userItems' + userId))
            .map(product => product[1]);
        var local_shipping_text = $('.local-shipping', $(this)).text()
            .match(RegExp(LOCAL_SHIPPING_COST), 'g');
        var local_shipping = local_shipping_text
            ? parseInt(local_shipping_text[0])
            : 0;
        $('#subtotalCostKRW', $(this)).html(
            userProducts.reduce((acc, product) => acc + product.costKRW, 0));
        $('#subtotalWeight', $(this)).html(
            userProducts.reduce((acc, product) => 
                acc + product.weight * product.quantity, 0));
        $('#subtotalShippingCostKRW', $(this)).html(
            userProducts.reduce((acc, product) => acc + product.shippingCostKRW, local_shipping));
        $('#subtotalTotalKRW', $(this)).html(
            userProducts.reduce((acc, product) => acc + product.totalKRW, local_shipping));
        $('#subtotalTotalRUR', $(this)).html(
            round_up(userProducts.reduce((acc, product) => 
                acc + product.totalKRW, 0) * currencyRates.RUR, 2));
        $('#subtotalTotalUSD', $(this)).html(
            round_up(userProducts.reduce((acc, product) => 
                acc + product.totalKRW, 0) * currencyRates.USD, 2));
        $('#subtotalTotalPoints', $(this)).html(
            userProducts.reduce((acc, product) => 
                acc + product.points * product.quantity, 0));
    });
}

function update_grand_subtotal() {
    var userProducts = Object.entries(g_cart);
    subtotal_krw = userProducts.reduce((acc, product) => acc + product[1].costKRW, 0);
    var local_shipping_fees = $('.local-shipping').text()
        .match(RegExp(LOCAL_SHIPPING_COST, 'g'))
    var local_shipping_cost = local_shipping_fees 
        ? local_shipping_fees.reduce((acc, cost) => acc + parseInt(cost), 0)
        : 0;
    var total_weight = userProducts.reduce((acc, product) => acc + product[1].weight * product[1].quantity, 0);
    box_weight = total_weight == 0 ? 0 : Object.entries(box_weights)
        .sort((a, b) => b[0] - a[0])
        .reduce((acc, box) => total_weight < box[0] ? box[1] : acc, 0);
    set_total_weight(total_weight + box_weight);
    var total_with_local_shipping_krw = subtotal_krw + local_shipping_cost
    $('#totalItemsCostKRW').html(total_with_local_shipping_krw);
    $('#totalItemsCostRUR').html(round_up(total_with_local_shipping_krw * currencyRates.RUR, 2));
    $('#totalItemsCostUSD').html(round_up(total_with_local_shipping_krw * currencyRates.USD, 2));
    $('[id^=totalItemsWeight]').html(totalWeight);
    if (box_weight) {
        $('.box-weight').show();
        $('#box-weight').text(box_weight);
    } else {
        $('.box-weight').hide();
    }
}

function validate_subcustomer(sender) {
    $.ajax({
        url: '/api/v1/order/subcustomer/validate',
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({subcustomer: sender.value}),
        success: data => {
            if (data.result) {
                if (data.result == 'success') {
                    $(sender).addClass('is-valid').removeClass('is-invalid');
                } else if (data.result === 'failure') {
                    modal(
                        'Subcustomer verification',
                        "Couldn't verify the subcustomer's credenticals. \n" +
                        "Problem subcustomer is: \n" + sender.value + "\n" +
                        data.message
                    );
                    $(sender).addClass('is-invalid').removeClass('is-valid');
                }
            }
        }
    })
}