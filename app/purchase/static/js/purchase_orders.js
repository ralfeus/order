var g_companies;
var g_editor;
var g_orders;
var g_purchase_orders_table;

$.fn.dataTable.ext.buttons.repost = {
    action: function(_e, _dt, _node, _config) {
        repost_failed(_dt.data({selected: true}));
    }
};

$(document).ready( function () {
    g_editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success_callback, error) => {
            $.ajax({
                url: '/api/v1/admin/purchase/order',
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(data.data[0]),
                success: data => success_callback(({data: [data]})),
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
            {label: 'Contact phone', name: 'contact_phone'}
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
        buttons: [
            { extend: 'create', editor: g_editor, text: 'Create purchase order' },
            { extend: 'repost', text: 'Re-post failed purchase orders'}
        ],
        columns: [
            {
                "className": 'purchase-order-actions',
                "orderable": false,
                "data": null,
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_purchase_order(this);">Open</button>'
            },
            {data: 'id'},
            {data: 'customer'},
            {data: 'total_krw'},
            {data: 'payment_account'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[6, 'desc']],
        select: true,
        serverSide: true,
        processing: true
    });
});

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
        url: '/api/v1/order?status=paid',
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

function repost_failed(target) {
    $.ajax({
        url: '/api/v1/admin/purchase/order/repost',
        method: 'post',
        complete: () => {
            g_purchase_orders_table.ajax.reload();
        }
    });
}