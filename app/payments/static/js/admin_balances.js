$.fn.dataTable.ext.buttons.status = {
    action: function(_e, dt, _node, _config) {
        set_status(dt.rows({selected: true}), this.text());
    }
};

$(document).ready( function () {
    init_balances_table();
});

function init_balances_table() {
    $('#balances').DataTable({
        dom: 'lfrtip',       
        ajax: {
            url: '/api/v1/admin/user',
            dataSrc: ''
        },
        columns: [
            {data: 'username'},
            {data: 'balance'}
        ],
        order: [[0, 'asc']],
        select: true
    });
}