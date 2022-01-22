var g_products = [];
var g_warehouse_id;

$(document).ready( function () {
    g_warehouse_id = $('#warehouse_id').val();
    get_dictionaries()
        .then(init_warehouse_products_table);
});

async function get_dictionaries() {
    g_products = await get_list('/api/v1/admin/product');
}

function init_warehouse_products_table() {
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/admin/warehouse/' + g_warehouse_id + '/product',
                contentType: 'application/json',
                data: data => JSON.stringify(data.data[0])
            },
            edit: {
                url: '/api/v1/admin/warehouse/' + g_warehouse_id + '/product/_id_',
                contentType: 'application/json',
                data: data => JSON.stringify(Object.entries(data.data)[0][1])
            },
            remove: {
                method: 'DELETE',
                url: '/api/v1/admin/warehouse/' + g_warehouse_id + '/product/_id_'
            }
        },
        table: '#warehouse_products',
        idSrc: 'product_id',
        fields: [
            { 
                name: 'product_id', 
                label: 'Product',
                type: 'select2',
                options: g_products.map(p => ({value: p.id, label: p.id + ': ' + p.name}))
            },
            { name: 'quantity', label: 'Quantity' }
        ]
    });

    g_warehouse_products_table = $('#warehouse_products').DataTable({
        lengthChange: false,
        buttons: [
            {extend: 'create', editor: editor},
            {extend: 'edit', editor: editor},
            {extend: 'remove', editor: editor},
            'pageLength'
        ],
        ajax: {
            url: '/api/v1/admin/warehouse/' + g_warehouse_id + '/product',
            dataSrc: 'data'
        },
        rowId: 'product_id',
        columns: [
            {name: 'product_id', data: 'product_id'},
            {
                data: 'product.name',
                render: (data, _d1, object) => 
                    "<a href=\"/admin/products?id=" + object.product_id + "\">" + 
                        data + "<br />" +
                        object.product.name_english + "<br />" +
                        object.product.name_russian + 
                    "</a>"
            },
            {data: 'quantity'}
        ],
        select: true,
        processing: true,
        initComplete: function() { 
            var table = this;
            this.api().buttons().container().appendTo( '#warehouse_products_wrapper .col-sm-12:eq(0)' ); 
        }
    });
}
