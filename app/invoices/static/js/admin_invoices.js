var g_invoice_table;
$.fn.dataTable.ext.buttons.xls = {
    extend: 'selected',
    action: function(e, dt, node, config) {
        get_excel(dt.rows({selected: true}));
    }
};

$(document).ready( function () {
    var editor = new $.fn.dataTable.Editor({
        table: '#invoices',
        idSrc: 'id',
        fields: [
            {label: "Customer name", name: 'customer'},
	    {label: "Export ID", name: "export_id"}
        ],
        ajax: {
	    edit: {
                url: '/api/v1/admin/invoice/_id_',
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: data => JSON.stringify(data.data[editor.ids()[0]])
            }
        }
    });
	//    Disable inline editing as more fields to edit emerge
//    $('#invoices').on( 'click', 'td.editable', function (e) {
//        editor.inline(this);
//    });  
    g_invoice_table = $('#invoices').DataTable({
        dom: 'lrBtip',
        ajax: {
            url: '/api/v1/admin/invoice'
        },
        buttons: [
            { extend: 'xls', text: 'Download' },
	    { extend: 'edit', text: 'Edit', editor: editor }
        ],
        columns: [
            {
                "className":      'invoice-actions',
                "orderable":      false,
                "data":           null,
                // "defaultContent": ''
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_invoice(this);">Open</button>'
            },
            {data: 'id'},
            {data: 'customer', className: 'editable'},
            {name: 'orders', data: row => row.orders.join()},
            {data: 'total'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        order: [[5, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        initComplete: function() { init_search(this); }
    });
});

function get_excel(rows) {
    $('.wait').show();
    if (rows.count() == 1) {
        window.open('/api/v1/admin/invoice/' + rows.data()[0].id + '/excel');
    } else {
        var invoices = '';
        for (var i = 0; i < rows.count(); i++) {
            invoices += 'invoices=' + rows.data()[i].id + '&';
        }
        window.open('/api/v1/admin/invoice/excel?' + invoices);
    }
    $('.wait').hide();
}

function open_invoice(target) {
    window.location = g_invoice_table.row($(target).parents('tr')).data().id;
}
