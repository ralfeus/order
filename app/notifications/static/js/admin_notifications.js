$(document).ready( function () {
    init_notifications_table();
});

function init_notifications_table() {
    var editor = $.fn.dataTable.editor({
        ajax: {
            create: {
                url: '/api/v1/admin/notification',
                data: d => JSON.stringify(d.data[0]),
                contentType: 'application/json'
            },
            edit: {
                url: '/api/v1/admin/notification/_id_',
                data: d => JSON.stringify(Object.entries(d.data)[0][1]),
                contentType: 'application/json'
            },
            remove: {
                type: 'DELETE',
                url: '/api/v1/admin/notification/_id_'
            }
        },
        table: '#notifications',
        idSrc: 'id',
        fields: [
            { label: 'Short description', name: 'short_desc' },
            { label: 'Long description', name: 'long_desc' }
        ]
    });
    $('#notifications').DataTable({
        dom: 'lfrtip',       
        ajax: {
            url: '/api/v1/admin/notification',
            dataSrc: ''
        },
        columns: [
            {data: 'id'},
            {data: 'short_desc'},
            {data: 'when_created'}
        ],
        order: [[2, 'desc']],
        select: true
    });
}