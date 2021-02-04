var g_amount = 0;
var g_amount_set_manually = false;
var g_currencies = [];
var g_customers = [];
var g_editor;
var g_payment_methods = [];
var g_payment_statuses = [];

$.fn.dataTable.ext.buttons.status = {
    action: function(_e, dt, _node, _config) {
        set_status(dt.rows({selected: true}), this.text());
    }
};

$(document).ready( function () {
    get_dictionaries()
        .then(init_payments_table);
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
    $('#currency_code', payment_details).text(data.currency_code);
    $('#amount_original', payment_details).val(data.amount_original);
    $('#amount_krw', payment_details).val(data.amount_krw);
    $('#amount_received_krw', payment_details).val(data.amount_received_krw);
    $('#additional_info', payment_details).text(data.additional_info);

    $('.currency-dropdown', payment_details).on('hidden.bs.dropdown', function(target) {
        $('#currency_code', payment_details).text(target.clickEvent.target.innerText);
        update_amount_krw(payment_details, data);
    });
    $('#amount_original', payment_details).on('change', function() {
        update_amount_krw(payment_details, data);
    });
    $('#amount_krw', payment_details).on('change', function() {
        data.amount_krw = this.value;
        
    });
    $('#amount_received_krw', payment_details).on('change', function() {
        data.amount_received_krw = this.value;
    });
    $('#evidence_image', payment_details).on('change', function() {
        if (this.files[0]) {
            this.nextElementSibling.textContent = 'File is specified';
        }
    });

    if (['approved', 'cancelled'].includes(data.status)) {
        $('.btn-save', payment_details).hide()
    } else {
        $('.btn-save', payment_details).on('click', function() {
            save_payment(row);
        })
    }

    for (var currency in g_currencies) {
        $('.dropdown-menu', payment_details).append(
            '<a class="dropdown-item" href="#">' + currency + '</a>'
        );
    }
    return payment_details;
}

async function get_dictionaries() {
    g_currencies = await get_currencies();
    g_customers = await get_users();
    g_payment_methods = await get_payment_methods();
    g_payment_statuses = (await get_list('/api/v1/payment/status'))
    g_filter_sources = {
        'payment_method.name': g_payment_methods.map(e => e.name),
        'status': g_payment_statuses
    };
}

function get_orders_to_pay(user) {
    get_list('/api/v1/admin/order?status=pending&user_id=' + user)
        .then(data => {g_editor.field('orders').update(data.map(o => o.id))});
}

function init_payments_table() {
    g_editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var payment_id = Object.entries(data.data)[0][0];
            var target = Object.entries(data.data)[0][1];
            target.evidences = target.evidences.map(e => ({
                id: e[0],
                file_name: g_editor.files().files[e].filename
            }));
            var method = 'post';
            var url = '/api/v1/payment/' + payment_id;
            if (data.action === 'create') {
                url = '/api/v1/payment';
                payment_id = target.id;
            }
            $.ajax({
                url: url,
                method: method,
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(target),
                success: data => {success(({data: [data]}))},
                error: error
            });
        },
        table: '#payments',
        idSrc: 'id',
        fields: [
            {
                label: 'Customer',
                name: 'user_id',
                type: 'select2',
                options: g_customers.map(c => ({
                    value: c.id,
                    label: c.username
                }))
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
                options: g_payment_methods.map(pm => ({
                    value: pm.id,
                    label: pm.name
                }))
            },
            {
                label: 'Currency',
                name: 'currency_code',
                type: 'select2',
                def: 'USD',
                options: g_currencies.map(c => c.code)
            },
            {label: 'Amount', name: 'amount_original'},
            {label: 'Amount (KRW)', name: 'amount_krw'},
            {label: 'Amount received', name: 'amount_received_krw'},
            {label: 'Additional info', name: 'additional_info', type: 'textarea'},
            {
                label: 'Evidence',
                name: 'evidences',
                type: 'uploadMany',
                ajax: '/api/v1/payment/evidence',
                display: (value, _file_num) => {
                    if (g_editor.files() && g_editor.files().files) {
                        return "" +
                            "<span class=\"small\">" + 
                            g_editor.files().files[value[0]].filename + 
                            "</span>";
                    } else {
                        return "\
                            <span class=\"small\"> \
                                <a target=\"_blank\" href=\"" + value.url + "\"> \
                                    " + value.file_name + " \
                                </a> \
                            </span>";
                    }
                }
            }
        ]
    });
    g_editor.on('open', on_editor_open);
    g_editor.field('user_id').input().on('change', on_customer_change);
    g_editor.field('currency_code').input().on('change', on_currency_change);
    g_editor.field('orders').input().on('change', on_orders_change);
    g_editor.field('amount_original').input().on('focus', function() {
        this.old_value = this.value});
    g_editor.field('amount_original').input().on('blur', on_amount_original_blur);

    var table = $('#payments').DataTable({
        dom: 'lrBtip',
        buttons: [
            // { extend: 'edit', editor: g_editor, text: "Edit payment"},
            { extend: 'create', editor: g_editor, text: 'Create' },
            { extend: 'edit', editor: g_editor, text: 'Edit' },
            { 
                extend: 'collection', 
                text: 'Set status',
                buttons: [
                    { extend: 'status', text: 'Approved' },
                    { extend: 'status', text: 'Rejected'}
                ]
            }
        ],        
        ajax: {
            url: '/api/v1/admin/payment',
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
            {data: 'user_name'},
            {data: 'orders'},
            {data: 'payment_method.name'},
            {data: 'amount_original_string'},
            {data: 'amount_krw'},
            {data: 'amount_received_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[9, 'desc']],
        select: true,
        footerCallback: function(row, data, start, end, display) {
            var api = this.api(), data;

            // // Remove the formatting to get integer data for summation
            // var intVal = function ( i ) {
            //     return typeof i === 'string' ?
            //         i.replace(/[\$,]/g, '')*1 :
            //         typeof i === 'number' ?
            //             i : 0;
            // };

            // Total over all pages
            totalSentOriginal = api
                .data()
                .reduce(function (accumulator, current) {
                    if (!accumulator[current.currency_code]) { 
                        accumulator[current.currency_code] = 0;
                    }
                    accumulator[current.currency_code] += current.amount_original;
                    return accumulator;
                }, {})
            totalSentOriginalString = Object.entries(totalSentOriginal)
                .map(e => e[0] + ": " + e[1].toLocaleString() + "<br />");
            totalSentKRW = api
                .column( 6 )
                .data()
                .reduce( function (a, b) {
                    return a + b;
                }, 0 );
            totalReceivedKRW = api
                .column( 7 )
                .data()
                .reduce( function (a, b) {
                    return a + b;
                }, 0 );

            // Update footer
            $(api.column(5).footer()).html(totalSentOriginalString);
            $( api.column(6).footer() ).html('₩' + totalSentKRW.toLocaleString());        
            $( api.column(7).footer() ).html('₩' + totalReceivedKRW.toLocaleString());        
        },
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
            // $('.btn-save').on('click', function() {
            //     var payment_node = $(this).closest('.payment-details');
            //     var update = {
            //         id: row.data().id,
            //         amount: $('#amount', payment_node).val(),
            //         evidence: $('#evidence', payment_node).val()
            //     };
            //     $('.wait').show();
            //     $.ajax({
            //         url: '/api/v1/admin/payment/' + update.id,
            //         method: 'post',
            //         dataType: 'json',
            //         contentType: 'application/json',
            //         data: JSON.stringify(update),
            //         complete: function() {
            //             $('.wait').hide();
            //         },
            //         success: function(data) {
            //             row.data(data).draw();
            //         }
            //     })
            // });
        }
    } );
}

function on_currency_change() {
    if (g_editor.field('currency_code').val()) {
        var currency_code = g_editor.field('currency_code').val();
        var currency = g_currencies.filter(c => c.code == currency_code)[0]
        if (!g_amount_set_manually) {
            g_editor.field('amount_original').val(g_amount * currency.rate);
        }
    }
    return {};
}

function on_amount_original_blur(data) {
    if (data.target.value != data.target.old_value) {
        g_amount_set_manually = true;
    }
}

function on_customer_change() {
    if (g_editor.field('user_id').val()) {
        get_orders_to_pay(g_editor.field('user_id').val());
    }
}

function on_editor_open() {
    g_amount_set_manually = false;
    //get_orders_to_pay();
}

function on_orders_change() {
    if (!g_amount_set_manually) {
        g_amount = 0;
        var orders = g_editor.field('orders').val();
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

function save_payment(row) {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/admin/payment/' + row.data().id,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            amount_original: row.data().amount_original,
            amount_krw: row.data().amount_krw,
            amount_received_krw: row.data().amount_received_krw,
            currency_code: row.data().currency_code
        }),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data) {
            row.data(data.payment).draw();
            if (data.message && data.message.length) {
                modal('Transaction save', data.message.join('<br />'));
            }
        }
    });

    var form_data = new FormData();
    form_data.append('file', $('#evidence_image', row.child())[0].files[0]);
    if (form_data) {
        $.ajax({
            url: '/api/v1/payment/' + row.data().id + '/evidence', 
            method: 'post',
            data: form_data, 
            contentType: false,
            cache: false,
            processData: false
        });
    }
}

/**
 * Sets status of the order
 * @param {*} target - table rows representing orders whose status is to be changed
 * @param {string} status - new status
 */
function set_status(target, newStatus) {
    if (target.count()) {
        $('.wait').show();
        var remained = 0;
        for (var i = 0; i < target.count(); i++) {
            remained++;
            $.ajax({
                url: '/api/v1/admin/payment/' + target.data()[i].id,
                method: 'POST',
                dataType: 'json', 
                contentType: 'application/json',
                data: JSON.stringify({
                    'status': newStatus,
                }),
                complete: function() {
                    remained--;
                    if (!remained) {
                        $('.wait').hide();
                    }
                },
                success: function(response, _status, _xhr) {
                    target.cell(
                        (_idx, data, _node) => 
                            data.id === parseInt(response.payment.id), 
                        5).data(response.payment.status).draw();
                    if (response.message && response.message.length) {
                        modal('Transaction save', response.message.join('<br />'));
                    }
                },
                error: xhr => {
                    modal("Transaction set status", xhr.responseText);
                }
            });     
        }
    } else {
        alert('Nothing selected');
    }
}

function update_amount_krw(target, target_data) {
    target_data.currency_code = $('#currency_code', target).text();
    target_data.amount_original = $('#amount_original', target).val();
    target_data.amount_krw = parseFloat(target_data.amount_original) / g_currencies[target_data.currency_code];
    $('#amount_krw', target).val(target_data.amount_krw);
    //target_data.draw();
}