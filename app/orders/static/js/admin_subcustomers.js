var g_filter_sources = {
    'in_network': [{id: 1, text: 'true'}, {id: 0, text: 'false'}]
};

$(document).ready( function () {
    var editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var target = Object.entries(data.data)[0][1];
            target.in_network = target.in_network[0];
            var subcustomer_id = Object.entries(data.data)[0][0];
            var method = 'post';
            var url = '/api/v1/admin/order/subcustomer/' + subcustomer_id;
            if (data.action === 'create') {
                url = '/api/v1/admin/order/subcustomer';   
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
                },
                error: data => {
                    modal('Subcustomer save', data.responseText);
                    error(data);
                }
            });
        },
        table: '#subcustomers',
        idSrc: 'id',
        fields: [
            {label: 'Name', name: 'name'},
            {label: 'Username', name: 'username'},
            {label: 'Password', name: 'password'},
            {
                label: 'In network', 
                name: 'in_network', 
                type: 'checkbox',
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            }
        ]
    });
    $('#subcustomers').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    });   
    var table = $('#subcustomers').DataTable({
        dom: 'lrBtip',
        buttons: [
            { extend: 'create', editor: editor, text: 'Create' },
            { extend: 'remove', editor: editor, text: 'Delete'}
        ],        
        ajax: {
            url: '/api/v1/admin/order/subcustomer',
            dataSrc: ''
        },
        rowId: 'id',
        columns: [
            {name: 'id', data: 'id'},
            {name: 'name', data: 'name', className: 'editable'},
            {name: 'username', data: 'username', className: 'editable'},
            {data: 'password', className: 'editable'},
            {name: 'in_network', data: 'in_network', className: 'editable'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[5, 'desc']],
        select: true,
        initComplete: function() { 
            var table = this;
            init_search(table, g_filter_sources)
            .then(() => init_table_filter(table)); 
        }
    });
});
