var g_customers = [];

$(document).ready(() => {
    get_dictionaries()
        .then(init_transactions_table);
});

function init_transactions_table() {
    var editor = new $.fn.dataTable.Editor({
        table: '#transactions',
        idSrc: 'id',
        ajax: {
            create: {
                url: '/api/v1/admin/payment/transaction',
                contentType: 'application/json',
                data: data => JSON.stringify(Object.entries(data.data)[0][1])
            }
        },
        fields: [
            {
                label: 'Customer',
                name: 'customer_id',
                type: 'select2',
                opts: {
                    ajax: {
                        url: '/api/v1/admin/user',
                        data: params => ({
                            q: params.term,
                            page: params.page || 1
                        }),
                        processResults: data => ({
                            results: data.results.map(i => ({
                                text: i.username,
                                id: i.id
                            })),
                            pagination: data.pagination
                        })
                    }
                }
            },
            {
                label: 'Amount',
                name: 'amount'
            }
        ]
    });
    $('#transactions').DataTable({
        dom: 'lrBtip',
        ajax: {
            url: '/api/v1/admin/payment/transaction'
        },
        buttons: [{extend:'create', text: 'Create', editor: editor}],
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
