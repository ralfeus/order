var g_pv_stats_table;

$(document).ready(() => {
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/pv_stats',
                data: data => JSON.stringify(Object.entries(data.data)[0][1]),
                contentType: 'application/json'
            },
            remove: {
                url: '/api/v1/pv_stats/_id_',
                method: 'DELETE',
                contentType: 'application/json'
            }
        },
        table: '#pv_stats',
        idSrc: 'node_id',
        fields: [
            {label: 'Node ID', name: 'node_id'}
        ]
    });          
    g_pv_stats_table = $('#pv_stats').DataTable({
        dom: 'rBtip',
        ajax: {
            url: '/api/v1/pv_stats',
            dataSrc: 'data'
        },
        buttons: [
            {extend: 'create', editor: editor, text: "New"},
            {extend: 'remove', editor: editor, text: "Remove"}
        ],
        rowId: 'node_id',
        rowGroup: {
            dataSrc: 'allowed',
            startRender: (rows, group) => {
                return group ? "Allowed" : "Pending";
            }
        },
        columns: [
            {
                data: 'is_being_updated',
                render: data => data ? '<img src="/static/images/loaderB16.gif" />' : ''
            },
            {data: 'node_id'},
            {data: 'node_name'},
            {data: 'network_pv'},
            {data: 'left_pv'},
            {data: 'right_pv'},
            {
                data: 'allowed',
                render: data => data ? "Allowed" : "Pending"
            },
            {data: 'when_updated'}
        ],
        select: true,
        processsing: true,
        initComplete: update_rows,
        order: [[1, 'asc']]
    });
});

async function update_rows(settings, data) {
    var api = new $.fn.dataTable.Api( settings );
    data.data.forEach(row => {
        var row_api = api.row(`#${row.node_id}`);
        if (row.update_now && !row.is_being_updated) {
            fetch(`/api/v1/pv_stats/${row.id}`).then(result => {
                result.json().then(response => {
                    row.network_pv = response.network_pv;
		    row.left_pv = response.left_pv;
		    row.right_pv = response.right_pv;
                    row.is_being_updated = false;
                    row_api.data(row).draw();
                });
            });
            $('td:eq(0)', row_api.node()).html('<img src="/static/images/loaderB16.gif" />');
        }
    });
}
