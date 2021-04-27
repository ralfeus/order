var g_order_drafts_table;

$(document).ready(init_order_drafts_table);

function init_order_drafts_table() {
    g_order_drafts_table = $('#order_drafts').DataTable({
        dom: 'lrtip',
        ajax: {
            url: '/api/v1/order?status=draft',
            error: xhr => { modal('No orders', xhr.responseText) },
            dataSrc: ''
        },
        columns: [
            {
                "className":      'order-actions',
                "orderable":      false,
                "data":           null,
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_order(this);">Open</button>'
            },
            {data: 'id'},
            {data: 'customer_name'},
            {data: 'total_krw'},
            {data: 'total_rur'},
            {data: 'total_usd'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[6, 'desc']],
        select: true
    });
}

function open_order(target) {
    window.location = g_order_drafts_table.row($(target).parents('tr')).data().id;
}