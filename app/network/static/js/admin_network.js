$(document).ready(() => {
    $('#network').DataTable({
        dom: 'lrtip',
        ajax: '/api/v1/admin/network',
        columns: [
            {data: 'id'},
            {data: 'name'},
            {data: 'rank'},
            {data: 'highest_rank'},
            {data: 'parent_id'},
            {data: 'left_id'},
            {data: 'right_id'},
            {data: 'signup_date'},
            {data: 'center'},
            {data: 'country'},
            {data: 'pv'},
            {data: 'network_pv'}
        ],
        serverSide: true,
        processing: true,
        select: true,
        initComplete: function() { init_search(this, null); }
    });
});