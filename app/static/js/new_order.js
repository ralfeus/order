var g_selected_shipping_method;
var g_products;
var g_cart = {};
var box_weights = {
    30000: 2200,
    20000: 1900,
    15000: 1400,
    10000: 1000,
    5000: 500,
    2000: 250
};
var itemsCount = {};
var currencyRates = {};
var users = 1;

var subtotalKRW = 0;
var totalWeight = 0;

var subcustomerTemplate;
var itemTemplate;

function roundUp(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}

$(document).ready(function() {
    itemTemplate = $('#userItems0_0')[0].outerHTML;
    subcustomerTemplate = $('.subcustomer-card')[0].outerHTML;

    $(document).on("click", "[id^=add_userItems]", (event) => add_product_row(event.target.id));
    $('#add_user').on('click', add_subcustomer);
    $('#submit').on('click', submit_order)

    get_countries();
    get_currencies();
    get_products()
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
    subtotalKRW = 0;
    totalWeight = 0;

    $('.subcustomer-card').remove();
    $('div#accordion').append(subcustomerTemplate);
    product_code_autocomplete($('.item-code'));
    product_quantity_change($('.item-quantity'));
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

function get_countries() {
    $.ajax({
        url: '/api/v1/country',
        success: function(data) {
            $('#country').html(data.map(c => '<option value="' + c.id + '">' + c.name + '</option>'))
            get_shipping_methods($('#country').val(), 0);
        }
    })
}

function get_currencies() {
    $.ajax({
        url: '/api/v1/currency',
        success: function(data, _status, _xhr) {
            currencyRates = data;
        }
    })
}

function get_products() {
    var promise = $.Deferred()
    $.ajax({
        url: '/api/v1/product',
        success: function(data) {
            if (data) {
                g_products = data.map(product => ({
                    'value': product.id,
                    'label': product.name_english + " | " + product.name_russian,
                    'price': product.price,
                    'points': product.points,
                    'weight': product.weight
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
    if ($('#shipping').val()) {
        g_selected_shipping_method = $('#shipping').val();
    }
    $('#shipping').html('');
    $.ajax({
        url: '/api/v1/shipping/' + country + '/' + weight,
        success: data => {
            $('#shipping').html(data.map(e => '<option value="' + e.id + '">' + e.name + '</option>'));
            if ($('#shipping option').toArray().map(i => i.value).includes(g_selected_shipping_method)) {
                $('#shipping').val(g_selected_shipping_method);
            }
            $.ajax({
                url: '/api/v1/shipping/rate/' + country + '/' + weight,
                success: data => {
                    shipping_rates = data;
                    get_shipping_cost($('#shipping').val(), weight);
                },
                error: xhr => {
                    $('.modal-title').text('Something went wrong...');
                    $('.modal-body').text(xhr.responseText);
                    $('.modal').modal();
                }
            })
        },
        error: (xhr) => {
            $('.modal-body').text(xhr.responseText);
            $('.modal').modal();
        }
    })
}

function product_code_autocomplete(target) {
    target.autocomplete({
        source: g_products,
        minLength: 1
    });
    target.on('change', () => product_line_fill(event.target));
}

function product_line_fill(line_input) {
    var product_line = $(line_input).closest('tr')[0];
    if (line_input.value) {
        $.ajax({
            url: '/api/v1/product/' + line_input.value,
            success: data => {
                $('.item-name', product_line).html(data[0].name_english + " | " + data[0].name_russian);
                $('.item-price', product_line).html(data[0].price);
                $('.item-points', product_line).html(data[0].points);
                g_cart[product_line.id] = data[0];
                update_item_subtotal($('.item-quantity', product_line));
            },
            error: (data) => {
                $('.modal-body').text(data.responseText);
                $('#modal').modal();
            }
        });
    } else {
        $('.item-name', product_line).html('');
        $('.item-price', product_line).html('');
        $('.item-points', product_line).html('');
        delete g_cart[product_line.id];
        update_item_subtotal($('.item-quantity', product_line));
    }
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
        url: '/api/v1/order',
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
            products: $('div.subcustomer-card').toArray().map(user => ({
                subcustomer: $('.subcustomer-identity', user).val(),
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
                window.alert("The request is posted. The request ID is " + data.order_id);
                clear_form();
            } else if (data.status === 'warning') {
                window.alert(
                    "The request is posted. The request ID is " + data.order_id +
                    "\nDuring request creation following issues have occurred:\n" +
                    message.join("\n")
                );
            } else if (data.status === 'error') {
                if (data.message) {
                    window.alert(data.message);
                } else {
                    window.alert("Unknown error has occurred. Contact administrator");
                }
            }
        },
        error: function(data, status, xhr) {
            window.alert("Unknown error has occurred. Contact administrator");
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
    $('#totalGrandTotalKRW').html(roundUp(
        parseFloat($('#totalItemsCostKRW').html()) + parseFloat($('#totalShippingCostKRW').html()), 2));
    $('#totalGrandTotalRUR').html(roundUp(
        parseFloat($('#totalItemsCostRUR').html()) + parseFloat($('#totalShippingCostRUR').html()), 2));
    $('#totalGrandTotalUSD').html(roundUp(
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
            $(this).html(roundUp(g_cart[$(this).parent().attr('id')].totalKRW * currencyRates.RUR, 2));
        } else {
            $(this).html('');
        }
    });
    $('.total-usd').each(function() {
        if (g_cart[$(this).parent().attr('id')]) {
            $(this).html(roundUp(g_cart[$(this).parent().attr('id')].totalKRW * currencyRates.USD, 2));
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
    $('#totalShippingCostRUR').html(roundUp(cost * currencyRates.RUR, 2));
    $('#totalShippingCostUSD').html(roundUp(cost * currencyRates.USD, 2));
    var product_weight = totalWeight - parseInt($('#box-weight').text())

    // Distribute shipping cost among items
    for (product in g_cart) {
        g_cart[product].shippingCostKRW = 
            roundUp(cost / product_weight * g_cart[product].weight * g_cart[product].quantity, 0);
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

/**
 * Update subtotal for single customer
 * @param {jQuery} target - div#userItems*
 */
function update_subcustomer_totals() { 
    $('.subcustomer-total').each(function(){
        var userId = parseInt(this.id.substr(14));
        var userProducts = Object.entries(g_cart)
            .filter(product => product[0].startsWith('userItems' + userId));

        $('#subtotalCostKRW', $(this)).html(
            userProducts.reduce((acc, product) => acc + product[1].costKRW, 0));
        $('#subtotalWeight', $(this)).html(
            userProducts.reduce((acc, product) => 
                acc + product[1].weight * product[1].quantity, 0));
        $('#subtotalShippingCostKRW', $(this)).html(
            userProducts.reduce((acc, product) => acc + product[1].shippingCostKRW, 0));
        $('#subtotalTotalKRW', $(this)).html(
            userProducts.reduce((acc, product) => acc + product[1].totalKRW, 0));
        $('#subtotalTotalRUR', $(this)).html(
            roundUp(userProducts.reduce((acc, product) => 
                acc + product[1].totalKRW, 0) * currencyRates.RUR, 2));
        $('#subtotalTotalUSD', $(this)).html(
            roundUp(userProducts.reduce((acc, product) => 
                acc + product[1].totalKRW, 0) * currencyRates.USD, 2));
        $('#subtotalTotalPoints', $(this)).html(
            userProducts.reduce((acc, product) => 
                acc + product[1].points * product[1].quantity, 0));
    });
}

function update_grand_subtotal() {
    var userProducts = Object.entries(g_cart);
    subtotalKRW = userProducts.reduce((acc, product) => acc + product[1].costKRW, 0);
    var total_weight = userProducts.reduce((acc, product) => acc + product[1].weight * product[1].quantity, 0);
    box_weight = total_weight == 0 ? 0 : Object.entries(box_weights)
        .sort((a, b) => b[0] - a[0])
        .reduce((acc, box) => total_weight < box[0] ? box[1] : acc, 0);
    set_total_weight(total_weight + box_weight);
    $('#totalItemsCostKRW').html(subtotalKRW);
    $('#totalItemsCostRUR').html(roundUp(subtotalKRW * currencyRates.RUR, 2));
    $('#totalItemsCostUSD').html(roundUp(subtotalKRW * currencyRates.USD, 2));
    $('[id^=totalItemsWeight]').html(totalWeight);
    if (box_weight) {
        $('.box-weight').show();
        $('#box-weight').text(box_weight);
    } else {
        $('.box-weight').hide();
    }
}
