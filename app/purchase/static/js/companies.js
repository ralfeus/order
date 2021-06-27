var g_addresses = [];

$(document).ready(() => {
    get_dictionaries()
    .then(init_table);
});

async function get_dictionaries() {
    g_addresses = await get_list('/api/v1/address');
}

function init_table() {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var target = Object.entries(data.data)[0][1];
            var company_id = Object.entries(data.data)[0][0];
            var method = 'post';
            var url = '/api/v1/admin/purchase/company/' + company_id;
            if (data.action === 'create') {
                url = '/api/v1/admin/purchase/company';   
                company_id = target.id;
            } else if (data.action === 'remove') {
                method = 'delete';
            }
            $.ajax({
                url: url,
                method: method,
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(target),
                success: data => {
                    success(({data: [data]}))
                    // update_totals()
                },
                error: error
            });
        },
        table: '#companies',
        idSrc: 'id',
        fields: [
            { label: 'Name', name: 'name' },
            {label: 'Tax_id', name: 'tax_id'},
            {label: 'Phone', name: 'phone'},
            { 
                label: 'Address',
                name: 'address_id',
                type: 'select2',
                options: g_addresses.map(c => ({
                    value: c.id,
                    label: c.name
                }))                
            },                 
            {label: 'Bank_id', name: 'bank_id'},
            {label: 'Contact_person', name: 'contact_person'},
        ]
    });
    $('#companies').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/purchase/company',
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
            {data: 'tax_id'},
            {data: 'phone'},
            {data: 'address.name'},
            {data: 'bank_id'},
            {data: 'contact_person'},
        ],
        select: true
    });
}