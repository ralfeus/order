$(document).ready( function () {
    init_notifications_table();
});

function init_notifications_table() {
    var editor = new $.fn.dataTable.Editor({
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
            { label: 'Long description', name: 'long_desc', type: 'text' }
        ]
    });
    $('#notifications').DataTable({
        dom: 'lfrBtip',       
        ajax: {
            url: '/api/v1/admin/notification',
            dataSrc: 'data'
        },
        buttons: [
            {extend: 'create', editor: editor, text: 'Create'},
            {extend: 'edit', editor: editor, text: 'Edit'},
            {extend: 'remove', editor: editor, text: 'Delete'}
        ],
        columns: [
            {data: 'id'},
            {data: 'short_desc'},
            {data: 'when_created'}
        ],
        order: [[2, 'desc']],
        select: true,
        serverSide: true,
        processing: true
    });
}