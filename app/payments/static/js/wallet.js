var editor;
var g_currencies;
var g_amount = 0;
var g_amount_set_manually = false;

$(document).ready( function () {
    get_dictionaries()
    .then(() => {
        init_payments_table();
        init_transactions_table();
    });
});

/**
 * Draws order product details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    var payment_details = $('.payment-details')
        .clone()
        .show(); 
    $('#evidence', payment_details).attr('src', '/' + data.evidence_image);
    return payment_details;
}

/**
 * Cancels payment request
 * @param {*} target - table rows representing orders whose status is to be changed
 * @param {string} status - new status
 */
function cancel(row) {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/payment/' + row.data().id,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            status: 'cancelled'
        }),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data) {
            row.data(data).draw();
        }
    });
}

async function get_dictionaries() {
    g_currencies = await get_currencies();
}

function get_orders_to_pay() {
    $.ajax({
        url: '/api/v1/order?status=pending',
        success: data => {
            editor.field('orders').update(data.map(o => o.id));
        }
    })
}

function get_payment_methods() {
    $.ajax({
        url: '/api/v1/payment/method',
        success: data => {
            editor.field('payment_method').update(data.map(pm => ({
                label: pm.name,
                value: pm.id
            })));
        }
    })
}

function init_payments_table() {
    editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            $.ajax({
                url: '/api/v1/payment',
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data.data[0]),
                success: data => {success(({data: [data]}))},
                error: error
            });
        },
        table: '#payments',
        idSrc: 'id',
        fields: [
            {
                label: 'Currency',
                name: 'currency_code',
                type: 'select2',
                def: 'USD',
                options: g_currencies.map(c => c.code)
            },
            {
                label: 'Orders', 
                name: 'orders',
                type: 'select2',
                opts: {
                    multiple: true
                }
            },
            {
                label: 'Payment method', 
                name: 'payment_method',
                type: 'select2'
            },
            {label: 'Amount', name: 'amount_original'},
            {
                label: 'Evidence',
                name: 'evidences',
                type: 'uploadMany',
                ajax: '/api/v1/payment/evidence',
                display: (value, file_num) => {
                    return '<img src="/upload/tmp/payment-evidence-' + value[file_num] + '" />';
                }
            }
        ]
    });
    editor.on('open', on_editor_open);
    editor.field('currency_code').input().on('change', on_currency_change);
    editor.field('orders').input().on('change', on_orders_change);
    editor.field('amount_original').input().on('focus', function(){this.old_value = this.value})
    editor.field('amount_original').input().on('blur', on_amount_original_blur);

    var table = $('#payments').DataTable({
        dom: 'lfrBtip',
        buttons: [
            { extend: 'create', editor: editor, text: 'Create new payment request' },
        ],        
        ajax: {
            url: '/api/v1/payment',
            dataSrc: ''
        },
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'id'},
            {data: 'orders'},
            {data: 'payment_method.name', defaultContent: ''},
            {data: 'amount_original_string'},
            {data: 'amount_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[7, 'desc']],
        select: true
    });


    $('#payments tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );

        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // First close all open rows
            $('tr.shown').each(function() {
                table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            row.child( format(row, row.data()) ).show();
            tr.addClass('shown');
            $('.btn-save').on('click', function() {
                var payment_node = $(this).closest('.payment-details');
                var update = {
                    id: row.data().id,
                    amount: $('#amount', payment_node).val(),
                    evidence: $('#evidence', payment_node).val()
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/v1/payment/' + update.id,
                    method: 'post',
                    dataType: 'json',
                    contentType: 'application/json',
                    data: JSON.stringify(update),
                    complete: function() {
                        $('.wait').hide();
                    },
                    success: function(data) {
                        row.data(data).draw();
                    }
                })
            });
            $('.btn-cancel').on('click', function() {cancel(row)});
        }
    } );
}

function init_transactions_table() {
    $('#transactions').DataTable({
        dom: 'lfrtip',
        ajax: {
            url: '/api/v1/payment/transaction',
            dataSrc: ''
        },
        columns: [
            {data: 'id'},
            {data: 'amount'},
            {data: 'customer_balance'},
            {data: 'created_by'},
            {data: 'when_created'}
        ],
        order: [[4, 'desc']],
        select: true
    });
}

function on_orders_change() {
    if (!g_amount_set_manually) {
        g_amount = 0;
        var orders = editor.field('orders').val();
        var orders_left = orders.length;
        for (var i = 0; i < orders.length; i++) {
            $.ajax({
                url: '/api/v1/order/' + orders[i],
                success: data => {
                    g_amount += data.total_krw;
                    if (!--orders_left) {
                        on_currency_change();
                    }
                }
            });
        }
    }
    return {};
}

function on_currency_change() {
    if (editor.field('currency_code').val()) {
        var currency_code = editor.field('currency_code').val();
        var currency = g_currencies.filter(c => c.code == currency_code)[0]
        if (!g_amount_set_manually) {
            editor.field('amount_original').val(g_amount * currency.rate);
        }
    }
    return {};
}

function on_amount_original_blur(data) {
    if (data.target.value != data.target.old_value) {
        g_amount_set_manually = true;
    }
}

function on_editor_open() {
    g_amount_set_manually = false;
    get_orders_to_pay();
    get_payment_methods();
}