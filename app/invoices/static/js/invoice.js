var g_editor;
var g_invoice;
var g_invoice_id = window.location.href.slice(-16);
var g_invoice_items_table;
var g_products;
var g_usd_rate;

$(document).ready(() => {
    get_usd()
	.then(get_invoice)
    .then(get_products)
    .then(init_invoices_table);
});

async function get_invoice() {
    g_invoice = (await (await fetch('/api/v1/admin/invoice/' + g_invoice_id)).json())[0];
    $('#export-id').val(g_invoice.export_id);
}

function init_invoices_table() {
    g_editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var invoice_item_id = Object.entries(data.data)[0][0];
            var method = 'post';
            var url = '/api/v1/admin/invoice/' + g_invoice_id + '/item/' + invoice_item_id;
            if (data.action === 'create') {
                url = '/api/v1/admin/invoice/' + g_invoice_id + '/item/new';   
            } else if (data.action === 'remove') {
                method = 'delete';
            }
            $.ajax({
                url: url,
                method: method,
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data.data[invoice_item_id]),
                success: data => {
                    success(({data: [data]}))
                    update_totals()
                },
                error: error
            });
        },
        table: '#invoice-items',
        idSrc: 'id',
        fields: [
            {
                label: 'Product ID', 
                name: 'product_id', 
                type: 'select2', 
                opts: {
                    ajax: {
                        url: '/api/v1/admin/product',
                        data: params => ({
                            q: params.term,
                            page: params.page || 1
                        }),
                        processResults: data => ({
                            results: data.results.map(i => ({
                                text: i.id + " | " + i.name,
                                id: i.id
                            })),
                            pagination: data.pagination
                        })
                    }
                }
            },
            {label: 'Price', name: 'price'},
            {label: 'Quantity', name: 'quantity', def: 1}
        ]
    });
    $('#invoice-items').on( 'click', 'td.editable', function (e) {
        g_editor.inline(this);
    } );    
    g_editor.field('product_id').input().on('change', event => {
        if (event.target.value) {
            g_editor.field('price').set(
                g_products.filter(obj => obj.value == event.target.value)[0].price);
        }
    } );        
    g_invoice_items_table = $('#invoice-items').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/invoice/' + g_invoice_id,
            dataSrc: json => json[0].invoice_items
        },
        buttons: [
            {extend: 'create', editor: g_editor, text: "New item"},
            {extend: 'remove', editor: g_editor, text: "Remove item"}
        ],
        columns: [
            {data: 'product_id', className: 'editable'},
            {data: 'product', class: 'wrapok'},
            {data: 'price', className: 'editable'},
            {data: 'quantity', className: 'editable'},
            {data: 'subtotal'}
        ],
        select: true,
        initComplete: update_totals
    });
}

function update_totals() {
    var total_weight = g_invoice_items_table.data().reduce((acc, row) => 
        acc + row.weight * row.quantity, 0);
    $('#total-weight').val(total_weight);
    var total = round_up(
        g_invoice_items_table.data().reduce((acc, row) => acc + row.price * row.quantity, 0), 
        2);
    $('#total').val(total);
}

function get_products() {
    var promise = $.Deferred()
    $.ajax({
        url: '/api/v1/product',
        success: function(data) {
            if (data) {
                g_products = data.map(product => ({
                    'value': product.id,
                    'label': product.name_english == null
                                ? product.name
                                : product.name_english,
                    'price': product.price * g_usd_rate,
                    'points': product.points,
                    'weight': product.weight
                }));
            }
            promise.resolve();
        }
    })
    return promise;
}

function get_excel() {
    window.open('/api/v1/admin/invoice/' + g_invoice_id + '/excel');
}

async function get_usd() {
    g_usd_rate = (await (await fetch('/api/v1/currency/USD')).json()).data[0].rate;
}

function round_up(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}
