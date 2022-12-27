// (function() {

var g_addresses;
var g_companies;
var g_customers;
var g_create_editor;
var g_edit_editor;
var g_filter_sources;
var g_orders;
var g_purchase_orders_table;
var g_po_statuses;
var g_vendors;

$.fn.dataTable.ext.buttons.repost = {
    extend: 'selected',
    action: function(_e, dt, _node, _config) {
        modal(
            "Repost purchase orders", 
            "Are you sure you want to post selected purchase orders again?",
            "confirmation")
        .then(result => {
            if (result == 'yes') {
                repost(dt.rows({selected: true}));
            }
        });
    }
};
$.fn.dataTable.ext.buttons.status_update = {
    action: function(_e, dt, _node, _config) {
        update_status(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    get_dictionaries().then(init_table).then(() => {
        var params = new URLSearchParams(window.location.search);
        if (params.get('action') == 'create') {
            create_po({
                order_id: params.get('order_id')
            });
        }
    });
});

function cancel_purchase_order(target) {
    g_create_editor
        .edit($(target).parents('tr')[0], false)
        .val('status', 'cancelled')
        .submit();
}

function create_po(params) {
    g_create_editor.field('order_id').def(params.order_id);
    g_create_editor.create();
}

function get_companies() {
    $.ajax({
        url: '/api/v1/admin/purchase/company_list',
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
    g_addresses = (await get_list('/api/v1/address')).map(
        a => ({
            value: a.id,
            label: a.name
        }));
    g_customers = (await get_list('/api/v1/admin/order/subcustomer')).map(
        s => ({
            value: s.id,
            label: s.name + " | " + s.username
        }));
    g_vendors = (await get_list('/api/v1/admin/purchase/vendor')).map(
        i => {
            entry = Object.entries(i)[0]; 
            return {value:entry[0], label:entry[1]};
        });
    g_po_statuses = await get_list('/api/v1/admin/purchase/status')
    g_filter_sources = {
        vendor: g_vendors.map(v => ({id: v.value, text: v.label})),
        status: g_po_statuses
    };
}

function get_orders_to_purchase(recreate=false) {
    console.debug('get_orders_to_purchase()')
    var promise = $.Deferred();
    $('.wait').show();
    $.ajax({
        url: '/api/v1/admin/order?status=can_be_paid&status=paid' + (recreate ? '&status=po_created' : ''),
        success: data => {
            $('.wait').hide();
            g_create_editor.field('order_id').update(data.map(o => o.id));
            console.debug('get_orders_to_purchase():exit')
            promise.resolve();
        },
        error: () => { promise.resolve(); }
    });
    return promise;
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
            data = data.data[0];
            data.purchase_restricted_products = data.purchase_restricted_products
                ? data.purchase_restricted_products[0]
                : false;
            data.recreate_po = data.recreate_po ? data.recreate_po[0] : false;
            $.ajax({
                url: url,
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data),
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
                label: 'Recreate purchase order',
                name: 'recreate_po',
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: false,
                unselectedValue: false
            },
            {
                label: 'Order', 
                name: 'order_id',
                type: 'select2'
            },    
            {
                label: 'Company', 
                name: 'company_id',
                type: 'select2',
                options: g_companies
            },
            {
                label: 'Address',
                name: 'address_id',
                type: 'select2',
                options: g_addresses
            },
            {label: 'Contact phone', name: 'contact_phone'},
            {
                label: 'Vendor',
                name: 'vendor',
                type: 'select2',
                def: 'AtomyQuick',
                options: g_vendors
            },
            {% for field in extension.fields %}
                {{ field }} ,
            {% endfor %}
        ]
    });
    g_create_editor.on('open', on_editor_open);
    g_create_editor.field('recreate_po').input().on('change', on_recreate_po_change);
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
                label: 'Customer',
                name: 'customer_id',
                type: 'select2',
                opts: {
                    ajax: {
                        url: '/api/v1/admin/order/subcustomer',
                        data: params => ({
                            q: params.term,
                            page: params.page || 1
                        }),
                        processResults: data => ({
                            results: data.results.map(i => ({
                                text: i.name + " | " + i.username,
                                id: i.id
                            })),
                            pagination: data.pagination
                        })
                    }
                }
            },
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
        g_edit_editor.inline(this, { onBlur: 'submit', drawType: 'none'});
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
            { extend: 'repost', text: 'Re-post selected POs'},
            { extend: 'status_update', text: 'Update selected POs status'}
        ],
        columns: [
            {
                "className": 'purchase-order-actions',
                "orderable": false,
                "data": null,
                'defaultContent': ''
            },
            {name: 'id', data: 'id'},
            {
                data: 'customer.name', 
                orderable: false,
                className: 'editable',
                editField: 'customer_id',
                render: function(data, type, row, meta) {
                    return "" +
                        "<span " +
                        "   class='subcustomer'" +
                        "   data-toggle=\"tooltip\" data-delay=\"{ show: 5000, hide: 3000}\"" +
                        "   title=\"Username: " + row.customer.username + "\nPassword: " + row.customer.password + "\">" +
                        "   <a href=\"/admin/orders/subcustomers?username=" + row.customer.username + "\">" +
                                data + 
                        "   </a>" +
                        "</span>";
                }
            },
            {
                data: 'total_krw', 
                orderable: false,
                render: (data, type, row, meta) => fmtKRW.format(data)
            },
            {data: 'purchase_date', className: 'editable', orderable: false},
            {name: 'purchase_restricted', data: 'purchase_restricted_products'},
            {name: 'company', data: 'company', orderable: false},
            {data: 'vendor', className: 'editable', orderable: false},
            {data: 'vendor_po_id', className: 'editable', orderable: false},
            {data: 'payment_account', className: 'editable', orderable: false},
            {
                data: 'status',
                render: function (data, type, row, meta) {
                    if (['failed', 'partially_posted'].includes(data)) {
                        return "<a href='#' onclick='show_po_status(\"" + row.id + "\")'>" + data + "</a>";
                    } else {
                        return data;
                    }
                },
                className: 'editable'
            },
            {data: 'when_created'},
            {data: 'when_changed'},
            {% for column in extension.columns %}
                {{ column }} ,
            {% endfor %}        
        ],
        order: [[11, 'desc']],
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
        initComplete: function() { 
            var table = this;
            init_search(table, g_filter_sources)
            .then(() => init_table_filter(table));
            if (table.DataTable().row(0).length == 0 ||
                table.DataTable().row(0).data().purchase_restricted_products === null) {
                table.DataTable().column('purchase_restricted:name').visible(false, true);
            }
        }
    });
}

async function on_editor_open() {
    console.debug('on_editor_open()')
    await get_orders_to_purchase();
    get_companies();
    if (g_purchase_orders_table.column('purchase_restricted:name').visible()) {
        g_create_editor.add({
            label: 'Purchase restricted products', 
            name: 'purchase_restricted_products', 
            type: 'checkbox', 
            options: [{label:'', value:true}],
            def: false,
            unselectedValue: false
        });
    }
    var default_order = g_create_editor.field('order_id').def();
    if (default_order) {
        g_create_editor.val('order_id', default_order);
    }
    console.debug('on_editor_open():exit')
}

function on_company_change() {
    if (g_create_editor.field('company_id').val()) {
        var company = g_companies.filter(c => c.id == g_create_editor.field('company_id').val())[0];
        g_create_editor.field('contact_phone').val(company.phone);
        g_create_editor.field('address_id').val(company.address.id);
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
    validate_po();
    return {};
}

async function on_recreate_po_change() {
    var promise = $.Deferred();
    if (g_create_editor.field('recreate_po').val()[0]) {
        modal(
            "Recreate purchase orders", 
            "All purchase orders for the selected order will be deleted and new will be created. Are you sure?",
            "confirmation")
        .then(async function (result) {
            if (result == 'yes') {
                await get_orders_to_purchase(recreate=true);
                promise.resolve();
            }
        });
    } else {
        await get_orders_to_purchase(recreate=false);
        promise.resolve();
    }
    return promise;
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

function repost(rows) {
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

async function validate_po() {
    var result = await (await fetch('/api/v1/admin/purchase/order/validate', {
        method: 'post',
        headers: {'Content-type': 'application/json'},
        body: JSON.stringify(g_create_editor.get())
    })).json();
    if (result.status == 'success') {
        g_create_editor.message('');
    } else if (result.status == 'error') {
        g_create_editor.message(`<span style="color: red;">${result.message}</div>`);
    }
}

// })()