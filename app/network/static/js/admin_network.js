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
        initComplete: function() { 
            init_search(this, null); 
        }
    });
    $('#nodes-count-input').appendTo('.btn-group');
    setInterval(updateBuilderStatus, 60000);
});

function updateBuilderStatus() {
    $.ajax({
        url: '/api/v1/admin/network/builder/status',
        success: data => {
            if (data['status'] === 'running') {
                set_builder_active();
            } else if (data['status'] === 'not running') {
                set_builder_inactive();
            } else {
                set_builder_error();
            }
        },
        error: () => {                
            set_builder_error();
        }
    });
}

function set_builder_active() {
    $('#green-circle').show();
    $('#red-circle').hide();
    $('#build').text('Stop');
    $('#build').off('click');
    $('#build').on('click', stop_builder);
    $('#build').prop('disabled', false);
}

function set_builder_inactive() {
    $('#green-circle').hide();
    $('#red-circle').show();
    $('#build').text('Update');
    $('#build').off('click');
    $('#build').on('click', start_builder);
    $('#build').prop('disabled', false);
}

function set_builder_error() {
    $('#green-circle').hide();
    $('#red-circle').hide();
    $('#build').text("Network Manager is unavailable");
    $('#build').prop('disabled', true);
}

function start_builder() {
    $.ajax({
        url: `/api/v1/admin/network/builder/start?nodes=${$('#nodes').val()}`,
        success: data => {
            if (data.status === 'started') {
                set_builder_active();
            }
        }
    });
}

function stop_builder() {
    $.ajax({
        url: '/api/v1/admin/network/builder/stop',
        success: data => {
            if (data.status === 'stopped') {
                set_builder_inactive();
            }
        }
    })
}
