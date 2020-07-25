å$.fn.dataTable.ext.buttons.create = {
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
            url: '/api/product',
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
            {data: 'points'},
            {data: 'name_english', visible: false},
            {data: 'name_russian', visible: false}
        ],
        select: true
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
                    points: row.data().points,
                    price: row.data().price,
                    weight: $('#weight', product_node).val()
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/product',
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
    // `d` is the original data object for the row
    return '<div class="container product-details">'+
        '<div class="row container">'+
            '<label class="col-1" for="name">Original name:</label>'+
            '<input id="name" class="form-control col-5" value="'+ d.name +'"/>'+
            '<label class="col-1" for="weight">Weight:</label>' +
            '<input id="weight" class="form-control col-1" value="' + d.weight + '"/>' +
            '<div class="col-3" />' + 
            '<input type="button" class="button btn-primary btn-save col-1" value="Save" />' +
        '</div>'+
        '<div class="row container">'+
            '<label class="col-1" for="name_english">English name:</label>'+
            '<input id="name_english" class="form-control col-5" value="' + d.name_english + '"/>'+
        '</div>'+
        '<div class="row container">'+
            '<label class="col-1" for="name_russian">Russian name:</label>'+
            '<input id="name_russian" class="form-control col-5" value="' + d.name_russian + '"/>'+
        '</div>'+
    '</div>';
}

function delete_product(rows) {
    rows.every(function() {
        var row = this
        $.ajax({
            url: '/api/product/' + row.data().id,
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