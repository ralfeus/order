$(document).ready( function () {
    init_warehouses_table();
});

function init_warehouses_table() {
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/admin/warehouse',
                contentType: 'application/json',
                data: data => {
                    data = Object.entries(data.data)[0][1];
                    data.is_local = data.is_local[0];
                    return JSON.stringify(data);
                }
            },
            edit: {
                url: '/api/v1/admin/warehouse/_id_',
                contentType: 'application/json',
                data: data => {
                    data = Object.entries(data.data)[0][1];
                    data.is_local = data.is_local[0];
                    return JSON.stringify(data);
                }
            },
            remove: {
                method: 'DELETE',
                url: '/api/v1/admin/warehouse/_id_'
            }
        },
        table: '#warehouses',
        idSrc: 'id',
        fields: [
            { name: 'name', label: 'Name' },
            {
                label: 'Local', 
                name: 'is_local', 
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            }
        ]
    });

    g_warehouses_table = $('#warehouses').DataTable({
        lengthChange: false,
        buttons: [
            {extend: 'create', editor: editor},
            {extend: 'edit', editor: editor},
            {extend: 'remove', editor: editor},
            'pageLength'
        ],
        ajax: {
            url: '/api/v1/admin/warehouse',
            dataSrc: 'data'
        },
        rowId: 'id',
        columns: [
            {name: 'id', data: 'id'},
            {
                data: 'name',
                render: (data, _d1, object) => "<a href=\"/admin/warehouses/" + object.id + "\">" + data + "</a>"
            },
            {data: 'is_local'},
            {data: 'when_created', render: dt_render_local_time},
            {data: 'when_changed', render: dt_render_local_time}
        ],
        select: true,
        processing: true,
        initComplete: function() { 
            var table = this;
            this.api().buttons().container().appendTo( '#warehouses_wrapper .col-sm-12:eq(0)' ); 
        }
    });
}
