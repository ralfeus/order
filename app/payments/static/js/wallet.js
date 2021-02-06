var editor;
var g_currencies;
var g_amount = 0;
var g_amount_set_manually = false;
var g_filter_sources;
var g_payment_methods;
var g_payment_statuses;

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
    data.evidences.forEach(evidence => {
        $('#evidences', payment_details).append(
            "<li><a target=\"_blank\" href=\"" + evidence.url + "\">" +
            evidence.file_name + "</a></li>");
    });
    return payment_details;
}

/**
 * Cancels payment request
 * @param {*} target - table rows representing orders whose status is to be changed
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
    g_payment_methods = (await get_payment_methods()).map(
        pm => ({value: pm.id, label: pm.name}));
    g_payment_statuses = await get_list('/api/v1/payment/status')
    g_filter_sources = {
        'payment_method.name': g_payment_methods.map(pm => pm.label),
        'status': g_payment_statuses
    }
}

function get_orders_to_pay() {
    $.ajax({
        url: '/api/v1/order?status=pending',
        success: data => {
            editor.field('orders').update(data.map(o => o.id));
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
                data: JSON.stringify({
                    additional_info: data.data[0].additional_info,
                    amount_original: data.data[0].amount_original,
                    currency_code: data.data[0].currency_code,
                    evidences: data.data[0].evidences.map(e => ({
                        id: e[0],
                        file_name: editor.files().files[e].filename
                    })),
                    orders: data.data[0].orders,
                    payment_method: data.data[0].payment_method
                }),
                success: data => {success(data)},
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
                name: 'payment_method.id',
                type: 'select2',
                options: g_payment_methods
            },
            {label: 'Amount', name: 'amount_original', def: 0},
            {label: 'Additional info', name: 'additional_info', type: 'textarea'},
            {
                label: 'Evidence',
                name: 'evidences',
                type: 'uploadMany',
                ajax: '/api/v1/payment/evidence',
                display: (value, _file_num) => {
                    return "" +
                        "<span class=\"small\">" + 
                        editor.files().files[value[0]].filename + 
                        "</span>";
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
        dom: 'lrBtip',
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
            {
                data: 'payment_method.name',
                defaultContent: '',
                fnCreatedCell: function (nTd, sData, oData, iRow, iCol) {
                    var instructions = oData.payment_method && oData.payment_method.instructions
                        ? oData.payment_method.instructions.replace(/\n/g, '<br />')
                        : "";
                    var method_name = oData.payment_method ? oData.payment_method.name : '';
                    $(nTd).html(
                        "<a href='#' onclick=\"modal('How to pay', '" 
                        + instructions + "')\">" + method_name + "</a>");
                }
            },
            {data: 'amount_original_string'},
            {data: 'amount_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[7, 'desc']],
        select: true,
        initComplete: function() { init_search(this, g_filter_sources); }
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
}