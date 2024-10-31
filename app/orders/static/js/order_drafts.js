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
                        onclick="open_order(this);">Open</button> \
                    <button \
                        class="btn btn-sm btn-danger btn-discard" \
                        onclick="discard_order(this);">Discard</button>'
            },
            {data: 'id'},
            {data: 'customer_name'},
            {data: 'total_krw'},
            {data: 'total_cur2'},
            {data: 'total_cur1'},
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

function discard_order(target) {
    modal(
        "Order draft discard", 
        "Are you sure you want to discard this order draft?",
        "confirmation")
    .then(result => {
        if (result == 'yes') {
            $('.wait').show();
            $.ajax({
                url: '/api/v1/order/' + 
                    g_order_drafts_table.row($(target).parents('tr')).data().id,
                method: 'delete',
                complete: function() {
                    $('.wait').hide();
                },
                success: () => {
                    g_order_drafts_table.row($(target).parents('tr')).remove().draw();
                },
                error: (response) => {
                    modal('Discard order draft error', response.responseText)
                }
            });
        }
    });
}