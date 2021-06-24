var g_customers = [];

$(document).ready(() => {
    get_dictionaries()
        .then(init_transactions_table);
});

function init_transactions_table() {
    $('#transactions').DataTable({
        dom: 'lrtip',
        ajax: {
            url: '/api/v1/admin/payment/transaction'
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
        order: [[6, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        initComplete: function() { 
            var table = this;
            init_search(table, g_filter_sources) 
            .then(() => init_table_filter(table));
        }
    });
}

async function get_dictionaries() {
    g_customers = (await get_list('/api/v1/admin/user')).map(
        item => ({ id: item.id, text: item.username }));
    g_filter_sources = {
        'customer': g_customers
    }
}
