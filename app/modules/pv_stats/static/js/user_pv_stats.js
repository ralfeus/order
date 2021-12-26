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
    $('#pv_stats').DataTable({
        dom: 'rBtip',
        ajax: {
            url: '/api/v1/pv_stats',
            dataSrc: 'data'
        },
        buttons: [
            {extend: 'create', editor: editor, text: "New"},
            {extend: 'remove', editor: editor, text: "Remove"}
        ],
        rowGroup: {
            dataSrc: 'allowed',
            startRender: (rows, group) => {
                return group ? "Allowed" : "Pending";
            }
        },
        columns: [
            {data: 'node_id'},
            {data: 'node_name'},
            {data: 'pv'},
            {data: 'network_pv'},
            {
                data: 'allowed',
                render: data => {
                    return data ? "Allowed" : "Pending";
                }
            },
            {data: 'when_updated'}
        ],
        select: true,
        processsing: true,
        rowCallback: update_row
    });
});

async function update_row(row, data, displayNum, displayIndex, dataIndex) {
    if (data.update_now && !data.is_being_updated) {
        fetch(`/api/v1/pv_stats/${data.id}/get`).then(result => {
            data.network_pv = result.network_pv;
        });
        $('td:eq(0)', row).html(`<img src="/static/images/wait.gif" />${$('td:eq(0)', row).html()}`);
    }
}