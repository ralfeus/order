var products = {};
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

function roundUp(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}

$(document).ready(function() {
    var itemTemplate = $('#userItems0_0')[0].outerHTML;
    subcustomerTemplate = $('.subcustomer-card')[0].outerHTML;

    $.ajax({
        url: '/api/currency',
        success: function(data, _status, _xhr) {
            currencyRates = data;
        }
    })

    $(document).on("click", "[id^=add_userItems]", function() {
        var id = this.id.substring(13)
        if (isNaN(itemsCount[id])) {
            itemsCount[id] = 1;
        } 
        var html = itemTemplate
            .replace(/userItems0_0/g, 'userItems' + id + '_' + itemsCount[id])
        $('#userItemsList' + id).append(html);
        product_code_autocomplete($('.item-code'));
        product_quantity_change($('.item-quantity'));
        itemsCount[id]++; 
    });

    $('#add_user').on('click', function() {
        var html = subcustomerTemplate
            .replace(/userItems([A-Za-z]*)0/g, 'userItems$1' + users)
            .replace(/identity0/g, "identity" + users)
            .replace(/(\w)\[0\]/g, '$1[' + users + ']')
        $('div#accordion').append(html);
        product_code_autocomplete($('.item-code'));
        product_quantity_change($('.item-quantity'));
        users++;
    });

    $('#submit').on('click', function() {
        $('.wait').show();
        $.ajax({
            url: '/api/order',
            method: 'post',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                name: $('#name').val(),
                address: $('#address').val(),
                country: $('#country').val(),
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
    })

    product_code_autocomplete($('.item-code'));
    product_quantity_change($('.item-quantity'));
});

function clear_form() {
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
        for (product in products) {
            if (product.match(new RegExp('userItems' + userId + '_\\d+'))) {
                delete products[product];
            }
        }
        $(target).parent().parent().remove();
        update_all_totals();
}

function delete_product(target) {
    var userItemId = target.id.substr(4);
    if(!userItemId.match(/userItems\d+_0/)) {
        delete products[userItemId];
        update_all_totals();
        $(target).parent().parent().remove();

    }
}

/**
 * Gets shipping cost for chosen country and weight
 * @param {number} totalWeight - total parcel weight
 */
function get_shipping_cost(totalWeight) {
    if (totalWeight == 0) {
        update_all_grand_totals(0, 0);
    } else {
        $.ajax({
            url: '/api/shipping_cost/' + $('#country').val() + '/' + totalWeight,
            success: function(data, _status, _xhr) {
                update_all_grand_totals(data.shipping_cost, totalWeight);
            },
            error: function(xhr, _status, _error) {
                alert(xhr.responseJSON.message);
                update_all_grand_totals(0, totalWeight);
            }
        });
    }
}

function product_code_autocomplete(target) {
    target.autocomplete({
        // source: "/api/product",
        source: function(request, response) {
            $.ajax({
                url: '/api/product/search/' + request.term,
                success: function(data) {
                    var result = data.map(product => ({
                        'value': product.id,
                        'label': product.name_english + " | " + product.name_russian,
                        'price': product.price,
                        'points': product.points,
                        'weight': product.weight
                    }));
                    response(result);
                },
                error: function() {
                    response({});
                }
            })
        },
        minLength: 1,
        select: function(_event, ui) {
            itemObject = $(this).parent().parent();
            $('td:nth-child(2)', itemObject).html(ui.item.label);
            $('td:nth-child(4)', itemObject).html(ui.item.price);
            $('td:nth-child(11)', itemObject).html(ui.item.points);
            products[itemObject.attr('id')] = ui.item;
            update_item_subtotal($('input.item-quantity', itemObject));
        }
    });
}

function product_quantity_change(target) {
    target.on('change', function() { update_item_subtotal($(this)); });
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
    get_shipping_cost(totalWeight);
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
    var productId = itemObject.attr('id');
    products[productId].user = '';
    products[productId].quantity = sender.val();
    products[productId].costKRW = products[productId].price * products[productId].quantity;
    $('td:nth-child(5)', itemObject).html(products[productId].costKRW);
    $('td:nth-child(6)', itemObject).html(products[productId].weight * products[productId].quantity);
    $('td:nth-child(12)', itemObject).html(products[productId].points * products[productId].quantity);
    update_all_totals();
}

function update_item_total() {
    $('.total-krw').each(function() {
        if (products[$(this).parent().attr('id')]) {
            $(this).html(products[$(this).parent().attr('id')].totalKRW);
        }
    });
    $('.total-rur').each(function() {
        if (products[$(this).parent().attr('id')]) {
            $(this).html(roundUp(products[$(this).parent().attr('id')].totalKRW * currencyRates.RUR, 2));
        }
    });
    $('.total-usd').each(function() {
        if (products[$(this).parent().attr('id')]) {
            $(this).html(roundUp(products[$(this).parent().attr('id')].totalKRW * currencyRates.USD, 2));
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

    // Distribute shipping cost among items
    for (product in products) {
        products[product].shippingCostKRW = 
            roundUp(cost / totalWeight * products[product].weight * products[product].quantity, 0);
        products[product].totalKRW = products[product].costKRW + products[product].shippingCostKRW;
    }
    $('.shipping-cost-krw').each(function() {
        if (products[$(this).parent().attr('id')]) {
            $(this).html(products[$(this).parent().attr('id')].shippingCostKRW);
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
        var userProducts = Object.entries(products)
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
    var userProducts = Object.entries(products);
    subtotalKRW = userProducts.reduce((acc, product) => acc + product[1].costKRW, 0);
    totalWeight = userProducts.reduce((acc, product) => acc + product[1].weight * product[1].quantity, 0);
    box_weight = totalWeight == 0 ? 0 : Object.entries(box_weights)
        .sort((a, b) => b[0] - a[0])
        .reduce((acc, box) => totalWeight < box[0] ? box[1] : acc, 0);
    totalWeight += box_weight;
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

