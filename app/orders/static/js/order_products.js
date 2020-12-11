$(document).ready( function () {
    var table = $('#order_products').DataTable({
        dom: 'lfrBtip',
        buttons: [
            'print',
            { 
                extend: 'selected', 
                text: 'Cancel',
                action: function(_e, dt, _node, _config) {
                    cancel(dt.rows({selected: true}));
                } 
            },
            { 
                extend: 'selected', 
                text: 'Postpone',
                action: function(_e, dt, _node, _config) {
                    postpone(dt.rows({selected: true}));
                } 
            }
        ],        
        ajax: {
            url: '/api/v1/order/product',
            dataSrc: 'data'
        },
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'order_id'},
            {data: 'suborder_id'},
            {data: 'id'},
            {data: 'subcustomer'},
            {data: 'product_id'},
            {data: 'product'},
            {data: 'quantity'},
            {data: 'status'},
            {data: 'public_comment', visible: false}
        ],

        select: true,
        serverSide: true,
        processing: true
    });

    $('#order_products tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // First close all open rows
            $('tr.shown').each(function() {
                table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            row.child( format(row, row.data()) ).show();
            tr.addClass('shown');
            $('.btn-save').on('click', function() {
                var product_node = $(this).closest('.product-details');
                var update = {
                    id: row.data().id,
                    public_comment: $('#public_comment', product_node).val()
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/v1/order/product/' + update.id,
                    method: 'post',
                    dataType: 'json',
                    contentType: 'application/json',
                    data: JSON.stringify(update),
                    complete: function() {
                        $('.wait').hide();
                    },
                    success: function(data) {
                        row.data(data).draw();
                    }
                })
            })
        }
    } );
});

function cancel(target) {
    target.data().toArray().forEach(op => {
        $.post('/api/v1/order/product/' + op.id + '/status/cancelled')
            .then(response => {
                target.cell(parseInt(response.id), 8)
                    .data(response.order_product_status).draw();
            });
    });
}

/**
 * Draws order product details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    return '<div class="container product-details">'+
        '<div class="row container">'+
            '<label class="col-5" for="public_comment">Public comment:</label>' +
            '<input type="button" class="button btn-primary btn-save col-1" value="Save" />' +
        '</div>' +
        '<div class="row container">' +
            '<textarea id="public_comment" class="form-control col-4">' + data.public_comment + '</textarea>' +
        '</div>'+
    '</div>';
}

function postpone(target) {
    target.data().toArray().forEach(op => {
        $.post('/api/v1/order/product/' + op.id + '/postpone')
            .then(response => {
                target.cell(parseInt(response.id), 8)
                    .data(response.order_product_status).draw();
            });
    });
}