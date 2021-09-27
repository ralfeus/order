var g_shipping_methods_table;

$(document).ready(() => {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: {
            url: '/api/v1/admin/shipping/_id_',
            contentType: 'application/json',
            data: data => {
                target = Object.entries(data.data)[0][1]
                target.enabled = target.enabled[0];
                return JSON.stringify(target);
            }
        },
        table: '#shipping_methods',
        idSrc: 'id',
        fields: [
            {label: 'Name', name: 'name'},
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
            {data: 'name'},
            {data: 'enabled'},
            {data: 'notification'}
        ],
        select: true
    });
});