var g_companies;
var g_create_editor;
var g_edit_editor;
var g_filter_sources;
var g_orders;
var g_purchase_orders_table;
var g_po_statuses;
var g_vendors;

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
    get_dictionaries().then(init_table);
});

function cancel_purchase_order(target) {
    g_create_editor
        .edit($(target).parents('tr')[0], false)
        .val('status', 'cancelled')
        .submit();
}

function get_companies() {
    $.ajax({
        url: '/api/v1/admin/purchase/company',
        success: data => {
            g_companies = data;
            g_create_editor.field('company_id').update(data.map(c => ({
                label: c.name,
                value: c.id
            })));
        }
    });
}

async function get_dictionaries() {
    // g_vendors = await get_vendors();
    g_vendors = (await get_list('/api/v1/admin/purchase/vendor')).map(
        i => {
            entry = Object.entries(i)[0]; 
            return {value:entry[0], label:entry[1]};
        });
    g_po_statuses = await get_list('/api/v1/admin/purchase/status')
    g_filter_sources = {
        'vendor': g_vendors.map(v => ({id: v.value, text: v.label})),
        'status': g_po_statuses
    };
}

function get_orders_to_purchase() {
    $.ajax({
        url: '/api/v1/admin/order?status=can_be_paid&status=paid',
        success: data => {
            // g_orders = data;
            g_create_editor.field('order_id').update(data.map(o => o.id));
        }
    })
}

async function get_vendors() {
    var vendors = (await get_list('/api/v1/admin/purchase/vendor')).map(
        i => {
            entry = Object.entries(i)[0]; 
            return {value:entry[0], label:entry[1]};
        });
    g_create_editor.field('vendor').update(vendors);
    g_create_editor.field('vendor').val('AtomyQuick');
    g_edit_editor.field('vendor').update(vendors);
    return vendors;
}

function init_table() {
    g_create_editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success_callback, error) => {
            var url = '/api/v1/admin/purchase/order';
            $.ajax({
                url: url,
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data.data[0]),
                success: (data, _status, xhr) => {
                    success_callback(data);
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
            {
                label: 'Vendor',
                name: 'vendor',
                type: 'select2',
                def: 'AtomyQuick',
                options: g_vendors
            }
        ]
    });
    g_create_editor.on('open', on_editor_open);
    g_create_editor.field('order_id').input().on('change', on_order_change);
    g_create_editor.field('company_id').input().on('change', on_company_change);

    var min_date = new Date();
    var backday = 3;
    if ([1, 2].includes(min_date.getDay())) { 
        backday += 2; 
    }
    min_date.setDate(min_date.getDate() - backday);
    g_edit_editor  = new $.fn.dataTable.Editor({
        ajax: {
            url: '/api/v1/admin/purchase/order/_id_',
            contentType: 'application/json',
            data: d => JSON.stringify(Object.entries(d.data)[0][1]),
            error: (xhr, _e, _a) => {
                modal("Purchase Order update failure", xhr.responseText);
            }
        },
        table: '#purchase_orders',
        idSrc: 'id',
        fields: [
            {
                label: 'Purchase date', 
                name: 'purchase_date',
                type: 'datetime',
                opts: {
                    firstDay: 1,
                    gotoCurrent: true,
                    minDate: min_date,
                    disableDays: [0, 6]
                }
            },
            {name: 'vendor', type: 'select2', options: g_vendors},
            {label: 'Vendor PO ID', name: 'vendor_po_id'},
            {label: 'Payment account', name: 'payment_account'},
            {
                label: 'Status', 
                name: 'status', 
                type: 'select2',
                options: g_po_statuses
            }
        ]
    });
    $('#purchase_orders').on( 'click', 'td.editable', function (e) {
        g_edit_editor.inline(this, { submitOnBlur: true });
    }); 

    g_purchase_orders_table = $('#purchase_orders').DataTable({
        dom: 'lrBtip',
        ajax: {
            url: '/api/v1/admin/purchase/order',
            error: xhr => { modal('No purchase orders', xhr.responseText) },
            dataSrc: 'data'
        },
        rowId: 'id',
        buttons: [
            { extend: 'create', editor: g_create_editor, text: 'Create purchase order' },
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
            {
                data: 'customer', 
                orderable: false,
                fnCreatedCell: function(nTd, sData, oData, iRow, iCol) {
                    $(nTd).html("" +
                        "<span " +
                        "    class='subcustomer'" +
                        "    data-toggle=\"tooltip\" data-delay=\"{ show: 5000, hide: 3000}\"" +
                        "    title=\"Username: " + oData.customer.username + "\nPassword: " + oData.customer.password + "\">" +
                            oData.customer.name + 
                        "</span>");
                }
            },
            {data: 'total_krw', orderable: false},
            {data: 'purchase_date', className: 'editable', orderable: false},
            {data: 'vendor', className: 'editable', orderable: false},
            {data: 'vendor_po_id', className: 'editable', orderable: false},
            {data: 'payment_account', className: 'editable', orderable: false},
            {
                data: 'status',
                fnCreatedCell: function (nTd, sData, oData, iRow, iCol) {
                    if (['failed', 'partially_posted'].includes(oData.status)) {
                        $(nTd).html("<a href='#' onclick='show_po_status(\"" + oData.id + "\")'>" + oData.status + "</a>");
                    }
                },
                className: 'editable'
            },
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[9, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        createdRow: (row, data) => {
            if (data.status == 'failed') {
                $(row).addClass('red-line');
            } else if (data.status == 'partially_posted') {
                $(row).addClass('orange-line');
            }
        },
        initComplete: function() { init_search(this, g_filter_sources); }
    });
}

function on_editor_open() {
    get_orders_to_purchase();
    get_companies();
}

function on_company_change() {
    if (g_create_editor.field('company_id').val()) {
        var company = g_companies.filter(c => c.id == g_create_editor.field('company_id').val())[0];
        g_create_editor.field('contact_phone').val(company.phone);
    }
}

function on_order_change() {
    if (g_create_editor.field('order_id').val()) {
        $.ajax({
            url: '/api/v1/transaction?order_id=' + g_create_editor.field('order_id').val(),
            success: data => {
                g_create_editor.field('company_id').val(data[0].payment_method.payee_id);
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
                var row = rows.select(data.id)
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
    // $('.wait').show();
    pos.forEach(po_id => {
        $.ajax({
            url: '/api/v1/admin/purchase/order/' + po_id + '?action=update_status',
            method: 'post',
            // complete: () => {
            //     if (!--pos_left) {
            //         $('.wait').hide();
            //     }
            // },
            success: (data, _status, xhr) => {
                var status_cell = g_purchase_orders_table.cell('#' + po_id, 5);
                status_cell
                    .data('<img src="/static/images/loaderB16.gif" />&nbsp;' + status_cell.data());
            },
            error: xhr => {
                modal('PO: Status update', "Couldn't update PO status. " + xhr.responseText);
            }
        });        
    });
}