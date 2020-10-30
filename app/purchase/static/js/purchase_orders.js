var g_companies;
var g_editor;
var g_orders;
var g_purchase_orders_table;

$.fn.dataTable.ext.buttons.repost = {
    action: function(_e, dt, _node, _config) {
        repost_failed(dt.rows({selected: true}));
    }
};
$.fn.dataTable.ext.buttons.status_update = {
    action: function(_e, dt, _node, _config) {
        update_status(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    g_editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success_callback, error) => {
            var url = '/api/v1/admin/purchase/order';
            if (data.action == 'edit') {
                url += '/' + data.data[0].id;
            }
            $.ajax({
                url: url,
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data.data[0]),
                success: (data, _status, xhr) => {
                    success_callback(({data: [data]}));
                    if (xhr.status == 202) {
                        poll_status();
                    }
                },
                error: error
            });     
        },
        table: '#purchase_orders',
        idSrc: 'id',
        fields: [
            {
                label: 'Order', 
                name: 'order_id',
                type: 'select2'
            },    
            {
                label: 'Company', 
                name: 'company_id',
                type: 'select2'
            },
            {label: 'Contact phone', name: 'contact_phone'},
            {label: 'Status', name: 'status', type: 'select2', visible: false}
        ]
    });
    g_editor.on('open', on_editor_open);
    g_editor.field('order_id').input().on('change', on_order_change);
    g_editor.field('company_id').input().on('change', on_company_change);

    g_purchase_orders_table = $('#purchase_orders').DataTable({
        dom: 'lfrBtip',
        ajax: {
            url: '/api/v1/admin/purchase/order',
            error: xhr => { modal('No purchase orders', xhr.responseText) },
            dataSrc: 'data'
        },
        rowId: 'id',
        buttons: [
            { extend: 'create', editor: g_editor, text: 'Create purchase order' },
            { extend: 'repost', text: 'Re-post selected failed POs'},
            { extend: 'status_update', text: 'Update selected POs status'}
        ],
        columns: [
            {
                "className": 'purchase-order-actions',
                "orderable": false,
                "data": null,
                'defaultContent': ''
                // "defaultContent": ' \
                //     <button \
                //         class="btn btn-sm btn-secondary btn-open" \
                //         onclick="open_purchase_order(this);">Open</button> \
                    // <button \
                    //     class="btn btn-sm btn-secondary btn-cancel" \
                    //     onclick="cancel_purchase_order(this);">Cancel</button>'
            },
            {data: 'id'},
            {data: 'customer'},
            {data: 'total_krw'},
            {data: 'payment_account'},
            {
                data: 'status',
                fnCreatedCell: function (nTd, sData, oData, iRow, iCol) {
                    if (oData.status == 'failed') {
                        $(nTd).html("<a href='#' onclick='show_po_status(\"" + oData.id + "\")'>" + oData.status + "</a>");
                    }
                }
            },
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[6, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        createdRow: (row, data) => {
            if (data.status == 'failed') {
                $(row).addClass('red-line');
            } else if (data.status == 'partially_posted') {
                $(row).addClass('orange-line');
            }
        }
    });
});

function cancel_purchase_order(target) {
    g_editor
        .edit($(target).parents('tr')[0], false)
        .val('status', 'cancelled')
        .submit();
}

function get_companies() {
    $.ajax({
        url: '/api/v1/admin/purchase/company',
        success: data => {
            g_companies = data;
            g_editor.field('company_id').update(data.map(c => ({
                label: c.name,
                value: c.id
            })));
        }
    });
}

function get_orders_to_purchase() {
    $.ajax({
        url: '/api/v1/admin/order?status=paid',
        success: data => {
            // g_orders = data;
            g_editor.field('order_id').update(data.map(o => o.id));
        }
    })
}

function on_editor_open() {
    get_orders_to_purchase();
    get_companies();
}

function on_company_change() {
    if (g_editor.field('company_id').val()) {
        var company = g_companies.filter(c => c.id == g_editor.field('company_id').val())[0];
        g_editor.field('contact_phone').val(company.phone);
    }
}

function on_order_change() {
    if (g_editor.field('order_id').val()) {
        $.ajax({
            url: '/api/v1/transaction?order_id=' + g_editor.field('order_id').val(),
            success: data => {
                g_editor.field('company_id').val(data[0].payment_method.payee_id);
            }
        })
    }
    return {};
}

function open_purchase_order(target) {
    window.location = g_purchase_orders_table.row($(target).parents('tr')).data().id;
}

function poll_status() {
    var data_reload = setInterval(() => {
        $.ajax({
            url: '/api/v1/admin/purchase/order?status=pending',
            error: () => {
                clearInterval(data_reload);
            }
        });
        g_purchase_orders_table.ajax.reload();
    }, 30000);
}

function repost_failed(rows) {
    var pos = rows.data().map(row => row.id).toArray();
    pos.forEach(po_id => {
        $.ajax({
            url: '/api/v1/admin/purchase/order/' + po_id + '?action=repost',
            method: 'post',
            success: (data, _status, xhr) => {
                var row = rows.select(data.id);
                row.data(data).draw();
                if (xhr.status == 202) {
                    poll_status();
                }
            }
        });        
    });
}

function show_po_status(po_id) {
    modal('', g_purchase_orders_table.row('#' + po_id).data().status_details);
}

function update_status(rows) {
    var pos = rows.data().map(row => row.id).toArray();
    pos_left = pos.length
    $('.wait').show();
    pos.forEach(po_id => {
        $.ajax({
            url: '/api/v1/admin/purchase/order/' + po_id + '?action=update_status',
            method: 'post',
            success: (data, _status, xhr) => {
                var row = rows.select(data.id);
                row.data(data).draw();
                if (!--pos_left) {
                    $('.wait').hide();
                }
            }
        });        
    });
}