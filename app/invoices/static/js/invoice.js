$(document).ready(() => {
    var editor = new $.fn.dataTable.Editor({
        table: '#invoice-items',
        idSrc: 'product_id',
        fields: [
            {label: 'Product ID', name: 'product_id'},
            {label: 'Price', name: 'price'},
            {label: 'Quantity', name: 'quantity'}
        ]
    });
    $('#invoice-items').on( 'click', 'td.editable', function (e) {
        editor.inline(this);
    } );            
    $('#invoice-items').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/invoice/' + window.location.href.slice(-16),
            dataSrc: json => json[0].invoice_items
        },
        buttons: [
            {extend: 'create', editor: editor}
        ],
        columns: [
            {data: 'product_id', className: 'editable'},
            {data: 'name', class: 'wrapok'},
            {data: 'price', className: 'editable'},
            {data: 'quantity', className: 'editable'},
            {data: 'subtotal'}
        ],
        select: true
    });
});