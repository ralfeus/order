$.fn.dataTable.ext.buttons.status = {
    action: function(e, dt, node, config) {
        setStatus(dt.rows({selected: true}), this.text());
    }
};

$(document).ready( function () {
    $('#orders').DataTable({
        dom: 'lfrBtip',
        buttons: [
            { extend: 'status', text: 'Pending' },
            { extend: 'status', text: 'Complete'}
        ],        
        ajax: {
            url: '/api/order_product',
            dataSrc: ''
        },
        columns: [
            {data: 'order_id'},
            {data: 'order_product_id'},
            {data: 'customer'},
            {data: 'subcustomer'},
            {data: 'product_id'},
            {data: 'product'},
            {data: 'quantity'},
            {data: 'comment'},
            {data: 'status'}
        ],

        select: true
    });
});

/**
 * Sets status of the order
 * @param {*} target - table rows representing orders whose status is to be changed
 * @param {string} status - new status
 */
function setStatus(target, newStatus) {
    if (target.count()) {
        var order_products = [];
        for (var i = 0; i < target.count(); i++) {
            order_products.push(target.data()[i].order_product_id);
            $.ajax({
                url: '/api/order_product/status/' + 
                    target.data()[i].order_product_id + '/' + newStatus,
                method: 'POST',
                success: function(response, status, xhr) {
                    target.cell(
                        (idx, data, node) => data.order_product_id === parseInt(response.order_product_id), 
                        8).data(response.order_product_status).draw();
                }
            });     
        }
    } else {
        alert('Nothing selected');
    }
}