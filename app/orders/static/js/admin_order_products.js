var g_order_product_statuses;

$.fn.dataTable.ext.buttons.status = {
    action: function(e, dt, node, config) {
        set_status(dt.rows({selected: true}), this.text());
    }
};

$(document).ready( function () {
    get_statuses().then(() => {
        var editor = new $.fn.dataTable.Editor({
            ajax: (_method, _url, data, success_callback, error) => {
                for (var order_product_id in data.data) {
                    $.ajax({
                        url: '/api/v1/admin/order/product/' + order_product_id,
                        method: 'post',
                        dataType: 'json',
                        contentType: 'application/json',
                        data: JSON.stringify(data.data[order_product_id]),
                        success: server_data => success_callback(({data: [server_data]})),
                        error: error
                    });     
                }    
            },
            table: '#order_products',
            idSrc: 'id',
            fields: [
                {label: 'Order product ID', name: 'id'},
                // {label: 'Customer', name: 'customer'},
                {label: 'Subcustomer', name: 'subcustomer'},
                {label: 'Product ID', name: 'product_id'},
                // {label: 'Product', name: 'product'},
                {label: 'Price', name: 'price'},
                {label: 'Quantity', name: 'quantity'},
                {label: 'Status', name: 'status'},
                {label: 'Private Comment', name: 'private_comment'},
                {label: 'Public Comment', name: 'public_comment'},
            ],
            // formOptions: {
            //     inline: {
            //         onBlur: 'submit'
            //     }
            // }
        });
        $('#order_products').on( 'click', 'tbody td.editable', function (e) {
            editor.inline( this);
        } );
        var table = $('#order_products').DataTable({
            dom: 'lfrBtip',
            buttons: [
                'print',
                {extend: 'edit', editor: editor},
                { 
                    extend: 'collection', 
                    text: 'Set status',
                    buttons: [ g_order_product_statuses.map(s => {
                        return {
                            extend: 'status',
                            text: s
                        }
                    })]
                }
            ],        
            ajax: {
                url: '/api/v1/admin/order/product',
                dataSrc: 'data'
            },
            columns: [
                {
                    "className":      'details-control',
                    "orderable":      false,
                    "data":           null,
                    "defaultContent": ''
                },
                {data: 'order_product_id'},
                {data: 'order_id'},
                {data: 'customer'},
                {data: 'subcustomer', className: 'editable'},
                {data: 'buyout_date'},
                {data: 'product_id', className: 'editable'},
                {data: 'product'},
                {data: 'price', className: 'editable'},
                {data: 'quantity', className: 'editable'},
                {data: 'status'},
                {data: 'when_created'}
            ],
            order: [[11, 'desc']],
            keys: {
                columns: '.editable',
                keys: [ 9 ],
                editor: editor,
                editOnFocus: true
            },
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
                        id: row.data().order_product_id,
                        private_comment: $('#private_comment', product_node).val(),
                        public_comment: $('#public_comment', product_node).val()
                    };
                    $('.wait').show();
                    $.ajax({
                        url: '/api/v1/admin/order/product/' + update.id,
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
});

/**
 * Draws order product details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    get_history(data.order_product_id, function(history_data) {
        $('#status_history', $(row.node()).next()).html(history_data.map(entry =>
            '<option>' + entry.when_created + " : " + entry.user + " : " + entry.status + "</option>"
        ).join("\n"));
    });
    return '<div class="container product-details">'+
        '<div class="row container">'+
            '<label class="col-5" for="private_comment">Private comment:</label>'+
            '<label class="col-5" for="public_comment">Public comment:</label>' +
            '<input type="button" class="button btn-primary btn-save col-1" value="Save" />' +
        '</div>' +
        '<div class="row container">' +
            '<textarea id="private_comment" class="form-control col-4">' + data.private_comment + '</textarea>' +
            '<div class="col-1">&nbsp;</div>' +
            '<textarea id="public_comment" class="form-control col-4">' + data.public_comment + '</textarea>' +
        '</div>'+
        '<div class="row container">' +
            '<select id="status_history" class="col-9" multiple></select>' +
        '</div>' +
    '</div>';
}

/**
 * Gets status history of the order product by its ID
 * @param {int} order_product_id 
 * @param {function(data)} callback - callback function to call with obtained data
 */
function get_history(order_product_id, callback) {
    $.ajax({
        url: '/api/v1/order/product/' + order_product_id + '/status/history',
        success: function(data) { callback(data); },
        error: function() {callback([]); }
    });
}

async function get_statuses() {
    data = await $.get('/api/v1/order/product/status');
    g_order_product_statuses = data;
}

/**
 * Sets status of the order
 * @param {*} target - table rows representing orders whose status is to be changed
 * @param {string} status - new status
 */
function set_status(target, newStatus) {
    if (target.count()) {
        var order_products = [];
        for (var i = 0; i < target.count(); i++) {
            order_products.push(target.data()[i].order_product_id);
            $.ajax({
                url: '/api/v1/order/product/' + 
                    target.data()[i].order_product_id + '/status/' + newStatus,
                method: 'POST',
                success: function(response, status, xhr) {
                    target.cell(
                        (idx, data, node) => 
                            data.order_product_id === parseInt(response.order_product_id), 
                        8).data(response.order_product_status).draw();
                    for (var ii = 0; ii < target.count(); ii++) {
                        if (target.data()[ii].order_product_id == response.order_product_id) {
                            if ($(target.nodes()[ii]).hasClass('shown')) {
                                get_history(response.order_product_id, function(history_data) {
                                    $('#status_history', $(target.nodes()[ii]).next()).html(history_data.map(entry =>
                                        '<option>' + entry.when_created + " : " + entry.user + " : " + entry.status + "</option>"
                                    ).join("\n"));
                                });
                            };                            
                            break;
                        }
                    }
                }
            });     
        }
    } else {
        alert('Nothing selected');
    }
}

