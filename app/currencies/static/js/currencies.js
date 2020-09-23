var g_currencies_table;

$(document).ready(() => {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var currency_item_id = Object.entries(data.data)[0][0];
            var method = 'post';
            var url = '/api/v1/admin/currency/' + g_currency_id + '/item/' + currency_item_id;
            if (data.action === 'create') {
                url = '/api/v1/admin/currency/' + g_currency_id + '/item/new';   
            } else if (data.action === 'remove') {
                method = 'delete';
            }
            $.ajax({
                url: url,
                method: method,
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data.data[currency_item_id]),
                success: data => {
                    success(({data: [data]}))
                    update_totals()
                },
                error: error
            });
        },
        table: '#currency-items',
        idSrc: 'id',
        fields: [
            {
                label: 'Currency ID', 
                name: 'currency_id', 
                type: 'autoComplete', 
                opts: {
                    source: (query, response) => {
                        var result = currency_id.filter(product =>
                            product.value.includes(query.term)
                            || product.label.includes(query.term)
                        );
                        response(result);
                    },
                    minLength: 2
                }
            },
            {label: 'Name', name: 'name'},
            {label: 'Rate', name: 'rate', def: 1}
        ]
    });
    $('#currency-items').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    } );    
    $('input', editor.field('currency_id').node()).on( 'blur', event => {
        editor.field('price').set(
            g_products.filter(obj => obj.value == event.target.value)[0].price);
    } );        
    g_currencies_table = $('#currency-items').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/currency/' + g_currency_table,
            dataSrc: json => json[0].currency_items
        },
        buttons: [
            {extend: 'create', editor: editor, text: "New item"},
            {extend: 'remove', editor: editor, text: "Remove item"}
        ],
        columns: [
            // {data: 'product_id', className: 'editable'},
            // {data: 'product', class: 'wrapok'},
            // {data: 'price', className: 'editable'},
            // {data: 'quantity', className: 'editable'},
            // {data: 'subtotal'}
        ],
        select: true,
        initComplete: update_totals
    });
});

// function update_totals() {
//     var total_weight = g_currency_items_table.data().reduce((acc, row) => 
//         acc + row.weight * row.quantity, 0);
//     $('#total-weight').val(total_weight);
//     var total = round_up(
//         g_invoice_items_table.data().reduce((acc, row) => acc + row.price * row.quantity, 0), 
//         2);
//     $('#total').val(total);
// }

// function get_products() {
//     var promise = $.Deferred()
//     $.ajax({
//         url: '/api/v1/product',
//         success: function(data) {
//             if (data) {
//                 g_products = data.map(product => ({
//                     'value': product.id,
//                     'label': product.name_english == null
//                                 ? product.name
//                                 : product.name_english,
//                     'price': product.price * g_usd_rate,
//                     'points': product.points,
//                     'weight': product.weight
//                 }));
//             }
//             promise.resolve();
//         }
//     })
//     return promise;
// }

// function get_excel() {
//     window.open('/api/v1/admin/invoice/' + g_invoice_id + '/excel');
// }

function get_usd() {
    var promise = $.Deferred()
    $.ajax({
        url: '/api/v1/currency',
        success: function(data) {
            if (data) {
                g_usd_rate = data.USD
            }
            promise.resolve();
        }
    })
    return promise;
}

function round_up(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}