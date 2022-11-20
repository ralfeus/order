var g_companies;

$(document).ready( function () {
    get_dictionaries().then(init_payment_methods_table);
});

async function get_dictionaries() {
    g_companies = (await get_list('/api/v1/admin/purchase/company')).map(
        e => ({label: e.name, value: e.id}));
}

function init_payment_methods_table() {
    function normalize_and_stringify(input) {
        input.enabled = input.enabled[0];
        return JSON.stringify(input);
    }

    var base_ajax = {
        contentType: 'application/json'
    };
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: $.extend(true, {}, base_ajax, {
                url: '/api/v1/admin/payment/method',
                data: d => normalize_and_stringify(d.data[0])
            }),
            edit: $.extend(true, {}, base_ajax, {
                url: '/api/v1/admin/payment/method/_id_',
                data: d => normalize_and_stringify(Object.entries(d.data)[0][1])
            }),
            remove: {
                type: 'DELETE',
                url: '/api/v1/admin/payment/method/_id_'
            }
        },
        table: '#payment_methods',
        idSrc: 'id',
        fields: [
            { label: 'Name', name: 'name' },
            { 
                label: 'Payee',
                name: 'payee_id',
                type: 'select2',
                options: g_companies
            },
            {
                label: 'Payment instructions',
                name: 'instructions',
                type: 'textarea'
            },
            {
                label: 'Enabled', 
                name: 'enabled', 
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            },
        ]
    });
    $('#payment_methods').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/payment/method',
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor, text: 'New'},
            {extend: 'edit', editor: editor, text: 'Edit'},
            {extend: 'remove', editor: editor, text: 'Delete'}
        ],
        columns: [
            {data: 'id'},
            {data: 'name'},
            {data: 'payee'},
            {data: 'enabled'}
        ],
        order: [[0, 'asc']],
        select: true
    });
}