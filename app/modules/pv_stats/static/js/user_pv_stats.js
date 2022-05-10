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
            {extend: 'remove', editor: editor, text: "Remove"},
            {
                extend: 'selected',
                text: "Update",
                action: (e, dt, node, config) => {
                    update_row(dt.row({selected: true}));
                }
            }
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
        columnDefs: [{
            targets: [3, 4, 5],
            render: $.fn.dataTable.render.number(' ', '.')
        }],
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
        if (row.update_now) {
            update_row(row_api);
        } else if (row.is_being_updated) {
            var interval_handler = setInterval(() => fetch_row(row_api, interval_handler), 60000);
        }
    });
}

function update_row(row_api) {
    var interval_handler = setInterval(() => fetch_row(row_api, interval_handler), 60000);
    fetch_row(row_api, interval_handler);
}

function fetch_row(row_api, interval_handler) {
    var row = row_api.data();
    if (!row.is_being_updated) {
        fetch(`/api/v1/pv_stats/${row.id}`).then(result => {
            if (result.status == 200) {
                result.json().then(response => {
                    row.network_pv = response.network_pv;
                    row.left_pv = response.left_pv;
                    row.right_pv = response.right_pv;
                    row.is_being_updated = response.is_being_updated;
                    row_api.data(row).draw();
                    clearInterval(interval_handler)
                });
            } else if (result.status != 202) { // permanent error
                    clearInterval(interval_handler)
            }
        })
        .catch(reason => {
            console.log(reason);
        })
        $('td:eq(0)', row_api.node()).html('<img src="/static/images/loaderB16.gif" />');
    }
}