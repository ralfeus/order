$.fn.dataTable.ext.buttons.create = {
    action: function(e, dt, node, config) {
        window.location = '/admin/product/new';
    }
};
$.fn.dataTable.ext.buttons.delete = {
    action: function(e, dt, node, config) {
        delete_product(dt.rows({selected: true}));
    }
}

$(document).ready( function () {
    var table = $('#products').DataTable({
        dom: 'lfrBtip', 
        ajax: {
            url: '/api/v1/admin/product',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({'all': true}),
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', text: 'Create'},
            {extend: 'delete', text: 'Delete'}
        ],
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'id'},
            {data: 'name'},
            {data: 'weight'},
            {data: 'price'},
            {data: 'points'}
        ],
        select: true,
        createdRow: (row, data) => {
            if (!data.available) {
                $(row).addClass('red-line');
            }
        }
    });

    $('#products tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // Open this row
            row.child( format(row.data()) ).show();
            tr.addClass('shown');
            $('.btn-save').on('click', function() {
                var product_node = $(this).closest('.product-details');
                var data = {
                    id: row.data().id,
                    name: $('#name', product_node).val(),
                    name_english: $('#name_english', product_node).val(),
                    name_russian: $('#name_russian', product_node).val(),
                    points: $('#points', product_node).val(),
                    price: $('#price', product_node).val(),
                    weight: $('#weight', product_node).val()
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/v1/admin/product',
                    method: 'post',
                    dataType: 'json',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    complete: function() {
                        $('.wait').hide();
                    },
                    success: function() {
                        row.data(data).draw();
                    }
                })
            })
        }
    } );
});

// Formatting function for row details
function format ( d ) {
    var product_details = $('.product-details')
    .clone()
    .show();
    $('#name', product_details).val(d.name);
    $('#name_english', product_details).val(d.name_english);
    $('#name_russian', product_details).val(d.name_russian);
    $('#weight', product_details).val(d.weight);
    $('#price', product_details).val(d.price);
    $('#points', product_details).val(d.points);
    return product_details;

}

function delete_product(rows) {
    rows.every(function() {
        var row = this
        $.ajax({
            url: '/api/v1/admin/product/' + row.data().id,
            method: 'delete',
            success: function() {
                row.remove().draw()
            },
            error: function(xhr, _status, _error) {
                alert(xhr.responseJSON.message);
            }
        });
    });
}