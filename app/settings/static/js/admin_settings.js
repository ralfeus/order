var g_settings_table;

$(document).ready(() => {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: {
            url: '/api/v1/admin/setting/_id_',
            contentType: 'application/json',
            data: data => JSON.stringify(Object.entries(data.data)[0][1])
        },
        table: '#settings',
        idSrc: 'key',
        fields: [
            {label: 'Value', name: 'value'}
        ]
    });
    $('#settings').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    });           
    g_settings_table = $('#settings').DataTable({
        dom: 'tp',
        ajax: {
            url: '/api/v1/admin/setting',
            dataSrc: ''
        },
        columns: [
            {
                data: 'key',
                render: (data, type, row, meta) => {
                    if (row.default_value == null) {
                        row.default_value = "";
                    }
                    if (row.value == null) {
                        row.value = "";
                    }
                    if (row.value != row.default_value) {
                        return '<strong>' + data + '</strong>';
                    } else {
                        return data;
                    }
                }
            },
            {data: 'value', className: 'editable'},
            {data: 'default_value'},
            {data: 'description'}
        ]
    });
});