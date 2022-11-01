$(document).ready( function () {
    init_order_packers_table();
});

function init_order_packers_table() {
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/admin/order/packer',
                contentType: 'application/json',
                data: data => {
                    data = Object.entries(data.data)[0][1];
                    data.is_local = data.is_local[0];
                    return JSON.stringify(data);
                }
            },
            edit: {
                url: '/api/v1/admin/order/packer/_id_',
                contentType: 'application/json',
                data: data => {
                    data = Object.entries(data.data)[0][1];
                    data.is_local = data.is_local[0];
                    return JSON.stringify(data);
                }
            },
            remove: {
                method: 'DELETE',
                url: '/api/v1/admin/order/packer/_id_'
            }
        },
        table: '#order_packers',
        idSrc: 'order_id',
        fields: [
            { name: 'name', label: 'Name' }
        ]
    });

    g_warehouses_table = $('#order_packers').DataTable({
        lengthChange: false,
        buttons: [
            {extend: 'create', editor: editor},
            {extend: 'edit', editor: editor},
            {extend: 'remove', editor: editor},
            'pageLength'
        ],
        ajax: {
            url: '/api/v1/admin/order/packer',
            dataSrc: 'data'
        },
        rowId: 'id',
        columns: [
            {name: 'order_id', data: 'order_id'},
            {data: 'name'},
            {data: 'when_created', render: dt_render_local_time},
            {data: 'when_changed', render: dt_render_local_time}
        ],
        select: true,
        processing: true,
        initComplete: function() { 
            var table = this;
            this.api().buttons().container().appendTo( '#order_packers_wrapper .col-sm-12:eq(0)' ); 
        }
    });
}
