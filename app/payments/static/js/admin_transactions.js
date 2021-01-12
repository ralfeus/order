var g_amount = 0;
var g_amount_set_manually = false;
var g_currencies = [];
var g_customers = [];
var g_editor;
var g_payment_methods = [];

$(document).ready(() => {
    init_transactions_table();
});

function init_transactions_table() {
    $('#transactions').DataTable({
        dom: 'lfrtip',
        ajax: {
            url: '/api/v1/admin/payment/transaction',
            dataSrc: ''
        },
        columns: [
            {data: 'id'},
            {data: 'order_id'},
            {data: 'customer'},
            {data: 'amount'},
            {data: 'customer_balance'},
            {data: 'created_by'},
            {data: 'when_created'}
        ],
        order: [[5, 'desc']],
        select: true
    });
}
