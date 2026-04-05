$(document).ready(() => {
    const table = $('#network').DataTable({
        dom: 'lrtip',
        ajax: {
            url: '/api/v1/admin/network',
            data: d => {
                const root = $('#filter-root').val().trim();
                if (root) d.root_id = root;
            }
        },
        columns: [
            {data: 'id'},
            {data: 'name'},
            {data: 'branch'},
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

    let filterDebounce;
    $('#filter-root').on('input', () => {
        clearTimeout(filterDebounce);
        filterDebounce = setTimeout(() => table.ajax.reload(), 500);
    });
    $('#filter-root-clear').on('click', () => {
        $('#filter-root').val('');
        table.ajax.reload();
    });

    table.on('draw', () => {
        const root = $('#filter-root').val().trim();
        if (!root) return;

        const ids = [];
        table.rows({page: 'current'}).data().each(row => ids.push(row.id));
        if (!ids.length) return;

        const params = new URLSearchParams({root_id: root});
        ids.forEach(id => params.append('ids', id));

        $.ajax({
            url: `/api/v1/admin/network/branch?${params.toString()}`,
            success: branches => {
                table.rows({page: 'current'}).every(function() {
                    const branch = branches[this.data().id];
                    if (branch !== undefined) {
                        $(this.cell(this.index(), 2).node()).text(branch);
                    }
                });
            }
        });
    });

    $('#nodes-count-input').appendTo('.btn-group');
    updateBuilderStatus();
    setInterval(updateBuilderStatus, 60000);
});

function updateBuilderStatus() {
    $.ajax({
        url: '/api/v1/admin/network/builder/status',
        success: data => {
            if (data['status'] === 'running') {
                set_builder_active(data);
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

function set_builder_active(data) {
    $('#green-circle').show();
    $('#red-circle').hide();
    $('#builder-status').attr('data-tooltip', data && data.progress ? data.progress : 'running');
    $('#build').text('Stop');
    $('#build').off('click');
    $('#build').on('click', stop_builder);
    $('#build').prop('disabled', false);
}

function set_builder_inactive() {
    $('#green-circle').hide();
    $('#red-circle').show();
    $('#builder-status').attr('data-tooltip', 'not running');
    $('#build').text('Update');
    $('#build').off('click');
    $('#build').on('click', open_build_dialog);
    $('#build').prop('disabled', false);
}

function set_builder_error() {
    $('#green-circle').hide();
    $('#red-circle').hide();
    $('#build').text("Network Manager is unavailable");
    $('#build').prop('disabled', true);
}

function open_build_dialog() {
    new bootstrap.Modal(document.getElementById('build-dialog')).show();
    $('#build-confirm').off('click').on('click', function() {
        bootstrap.Modal.getInstance(document.getElementById('build-dialog')).hide();
        start_builder();
    });
}

function start_builder() {
    const root = $('#build-root').val();
    const nodes = $('#build-nodes').val();
    const params = new URLSearchParams();
    if (nodes) params.set('nodes', nodes);
    if (root) params.set('root', root);
    $.ajax({
        url: `/api/v1/admin/network/builder/start?${params.toString()}`,
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
