var g_currencies_table;

$(document).ready(() => {
    function normalize_and_stringify(input) {
        input.enabled = input.enabled[0] === true;
        return JSON.stringify(input);
    }
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/admin/currency',
                data: data => normalize_and_stringify(Object.entries(data.data)[0][1]),
                contentType: 'application/json'
            },
            edit: {
                url: '/api/v1/admin/currency/_id_',
                data: data => normalize_and_stringify(Object.entries(data.data)[0][1]),
                contentType: 'application/json'
            },
            remove: {
                url: '/api/v1/admin/currency/_id_',
                method: 'DELETE',
                contentType: 'application/json'
            }
        },
        table: '#currencies',
        idSrc: 'code',
        fields: [
            {label: 'Currency code', name: 'code'},
            {label: 'Name', name: 'name'},
            {label: 'Rate', name: 'rate', def: 1},
            {
                label: 'Enabled', 
                name: 'enabled', 
                type: 'checkbox',                 
                options:   [
                    { label: '', value: true }
                ]
            }
        ]
    });
    $('#currencies').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    });           
    g_currencies_table = $('#currencies').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/currency',
            dataSrc: 'data'
        },
        buttons: [
            {extend: 'create', editor: editor, text: "New item"},
            {extend: 'remove', editor: editor, text: "Remove item"}
        ],
        columns: [
            {data: 'code', className: 'editable'},
            {data: 'name', className: 'editable'},
            {data: 'rate', className: 'editable'},
            {data: 'enabled', className: 'editable'}
        ],
        select: true
    });
});