// $.fn.dataTable.ext.buttons.status = {
//     action: function(e, dt, node, config) {
//         setStatus(dt.rows({selected: true}), this.text());
//     }
// };

$(document).ready( function () {
    var table = $('#order_products').DataTable({
        dom: 'lfrBtip',
        buttons: [
	        'print'//,
            // { 
            //     extend: 'collection', 
            //     text: 'Set status',
            //     buttons: [
            //         { extend: 'status', text: 'Pending' },
            //         { extend: 'status', text: 'Complete'}
            //     ]
            // }
        ],        
        ajax: {
            url: '/api/v1/order_product',
            dataSrc: ''
        },
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'order_id'},
            {data: 'order_product_id'},
            {data: 'subcustomer'},
            {data: 'product_id'},
            {data: 'product'},
            {data: 'quantity'},
            {data: 'status'},
            {data: 'public_comment', visible: false}
        ],

        select: true
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
                    public_comment: $('#public_comment', product_node).val()
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/order_product/' + update.id,
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

// /**
//  * Sets status of the order
//  * @param {*} target - table rows representing orders whose status is to be changed
//  * @param {string} status - new status
//  */
// function setStatus(target, newStatus) {
//     if (target.count()) {
//         var order_products = [];
//         for (var i = 0; i < target.count(); i++) {
//             order_products.push(target.data()[i].order_product_id);
//             $.ajax({
//                 url: '/api/order_product/' + 
//                     target.data()[i].order_product_id + '/status/' + newStatus,
//                 method: 'POST',
//                 success: function(response, status, xhr) {
//                     target.cell(
//                         (idx, data, node) => 
//                             data.order_product_id === parseInt(response.order_product_id), 
//                         8).data(response.order_product_status).draw();
//                     for (var ii = 0; ii < target.count(); ii++) {
//                         if (target.data()[ii].order_product_id == response.order_product_id) {
//                             if ($(target.nodes()[ii]).hasClass('shown')) {
//                                 get_history(response.order_product_id, function(history_data) {
//                                     $('#status_history', $(target.nodes()[ii]).next()).html(history_data.map(entry =>
//                                         '<option>' + entry.set_at + " : " + entry.set_by + " : " + entry.status + "</option>"
//                                     ).join("\n"));
//                                 });
//                             };                            
//                             break;
//                         }
//                     }
//                 }
//             });     
//         }
//     } else {
//         alert('Nothing selected');
//     }
// }
