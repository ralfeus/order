var g_addresses_table;

$(document).ready(() => {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var target = Object.entries(data.data)[0][1];
            var address_id = Object.entries(data.data)[0][0];
            var method = 'post';
            var url = '/api/v1/admin/address/' + address_id;
            if (data.action === 'create') {
                url = '/api/v1/admin/address';   
                address_id = target.id;
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
        table: '#addresses',
        idSrc: 'id',
        fields: [ 
            {label: 'Name', name: 'name'},
            {label: 'Zip', name: 'zip'},
            {label: 'Address 1', name: 'address_1'},
            {label: 'Address 2', name: 'address_2'},
            {label: 'Address 1 (eng)', name: 'address_1_eng'},
            {label: 'Address 2 (eng)', name: 'address_2_eng'},
            {label: 'City (eng)', name: 'city_eng'},
            {label: 'Delivery comment', name: 'delivery_comment'}
        ]
    });
    $('#addresses').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    });           
    g_addresses_table = $('#addresses').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/address',
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor, text: "New item"},
            {extend: 'edit', editor: editor, text: "Edit item"},
            {extend: 'remove', editor: editor, text: "Remove item"},
        ],
        columns: [
            {data: 'id', className: 'editable'},
            {data: 'name', className: 'editable'},
            {data: 'zip', className: 'editable'},
            {data: 'address_1', className: 'editable'},
            {data: 'address_2', className: 'editable'},
            
        ],
        select: true
    });
});