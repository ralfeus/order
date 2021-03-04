var g_currencies_table;

$(document).ready(() => {
    var editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var target = Object.entries(data.data)[0][1];
            var currency_id = Object.entries(data.data)[0][0];
            var method = 'post';
            var url = '/api/v1/admin/currency/' + currency_id;
            if (data.action === 'create') {
                url = '/api/v1/admin/currency/';   
                currency_id = target.code;
            } else if (data.action === 'remove') {
                method = 'delete';
            }
            $.ajax({
                url: url,
                method: method,
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(target),
                success: data => {
                    success(({data: [data]}))
                    // update_totals()
                },
                error: error
            });
        },
        table: '#currencies',
        idSrc: 'code',
        fields: [
            {
                label: 'Currency code', 
                name: 'code', 
                
            },
            {label: 'Name', name: 'name'},
            {label: 'Rate', name: 'rate', def: 1}
        ]
    });
    $('#currencies').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    });           
    g_currencies_table = $('#currencies').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/currency',
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor, text: "New item"},
            {extend: 'remove', editor: editor, text: "Remove item"}
        ],
        columns: [
            {data: 'code', className: 'editable'},
            {data: 'name', className: 'editable'},
            {data: 'rate', className: 'editable'}
        ],
        select: true
    });
});