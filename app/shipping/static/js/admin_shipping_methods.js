var g_shipping_methods_table;

function normalize_and_stringify(input) {
    target = Object.entries(input)[0][1]
    target.enabled = target.enabled[0];
    return JSON.stringify(target);
}

$(document).ready(() => {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/admin/shipping/_id_',
                contentType: 'application/json',
                data: data => normalize_and_stringify(data.data)
            },
            edit: {
                url: '/api/v1/admin/shipping/_id_',
                contentType: 'application/json',
                data: data => normalize_and_stringify(data.data)
            },
            remove: {
                url: '/api/v1/admin/shipping/_id_',
                method: 'delete'
            }
        },
        table: '#shipping_methods',
        idSrc: 'id',
        fields: [
            {label: 'Name', name: 'name'},
            {
                label: 'Type',
                name: 'type',
                type: 'select2',
                options: [{value: 'weight_based', label: 'Weight based'}]
            },
            {
                label: 'Enabled', 
                name: 'enabled',
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            },
            {label: 'Notification', name: 'notification'}
        ]
    });
    g_shipping_methods_table = $('#shipping_methods').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/shipping',
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor},
            {extend: 'edit', editor: editor},
            {extend: 'remove', editor: editor}
        ],
        columns: [
            {data: 'id'},
            {
                data: 'name',
                render: (data, _d1, object) => 
                    object.edit_url ? `<a href="${object.edit_url}">${data}</a>` : data
            },
            {data: 'type'},
            {data: 'enabled'},
            {data: 'notification'}
        ],
        select: true
    });
});