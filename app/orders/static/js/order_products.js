var g_filter_sources;
var g_order_product_statuses;

$(document).ready( function () {
    get_dictionaries().then(init_order_products_table);
});

function cancel(target) {
    target.data().toArray().forEach(op => {
        $.ajax({
            url: '/api/v1/order/product/' + op.id,
            method: 'delete'
        })
        .then(response => {
            target.row(parseInt(response.id)).remove().draw();
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

async function get_dictionaries() {
    g_order_product_statuses = await get_list('/api/v1/order/product/status')
    g_filter_sources = {
        'status': g_order_product_statuses
    };
}

function init_order_products_table() {
    var table = $('#order_products').DataTable({
        dom: 'lrBtip',
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
            {name: 'status', data: 'status'},
            {data: 'public_comment', visible: false}
        ],
        select: true,
        serverSide: true,
        processing: true,
        initComplete: function() { 
            init_search(this, g_filter_sources) 
            $('td:nth-child(' + (table.column('status:name').index() + 1) + ') select', 
                $(table.column('status:name').header()).closest('thead'))
                .val('po_created').trigger('change');
        }
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
}

function postpone(target) {
    target.data().toArray().forEach(op => {
        $.post('/api/v1/order/product/' + op.id + '/postpone')
            .then(response => {
                modal("Postpone order product", 
                 "The product is moved to sale order " + response.new_order_id);
                target.cell(parseInt(response.id), 8)
                    .data(response.order_product_status).draw();
            })
            .fail(error => {
                modal('Postpone order product', error.responseText);
            });
    });
}