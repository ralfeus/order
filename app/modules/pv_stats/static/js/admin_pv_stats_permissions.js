var g_pv_stats_permissions_table;
var g_filter_sources;
var g_statuses;

$(document).ready(() => {
    get_dictionaries()
    .then(init_table);
});

async function get_dictionaries() {
    g_statuses = [{id: false, text: 'Pending'}, {id: true, text: 'Allowed'}];
    g_filter_sources = {
        'allowed': g_statuses,
    };
}

function init_table() {
    $.fn.dataTable.ext.buttons.allow = {
        extend: 'selected',
        action: function(e, dt, node, config) {
            set_status(dt.rows({selected: true}), true);
        }
    };
    $.fn.dataTable.ext.buttons.deny = {
        extend: 'selected',
        action: function(e, dt, node, config) {
            set_status(dt.rows({selected: true}), false);
        }
    };
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/pv_stats',
                data: data => JSON.stringify(Object.entries(data.data)[0][1]),
                contentType: 'application/json'
            },
            remove: {
                url: '/api/v1/pv_stats/_id_',
                method: 'DELETE',
                contentType: 'application/json'
            }
        },
        table: '#pv_stats_permissions',
        idSrc: 'id',
        fields: [
            {label: 'Node ID', name: 'node_id'}
        ]
    });          
    g_pv_stats_permissions_table = $('#pv_stats').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/pv_stats/permission',
            dataSrc: 'data'
        },
        rowId: 'id',
        buttons: [
            {extend: 'create', editor: editor, text: "New"},
            {extend: 'remove', editor: editor, text: "Remove"},
            {extend: 'allow', text: "Allow"},
            {extend: 'deny', text: "Deny"}
        ],
        columns: [
            {data: 'user_id'},
            {data: 'node_id'},
            {data: 'allowed'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        select: true,
        initComplete: function() { 
            var table = this;
            init_search(table, g_filter_sources) 
            .then(() => init_table_filter(table));
        }
    });
}

function set_status(target, new_status) {
    modal(
        "PV stats permission request status change", 
        "Are you sure you want to change requests status to &lt;" + (new_status ? 'allow' : 'deny') + "&gt;?",
        "confirmation")
    .then(result => {
        if (result == 'yes') {
            $('.wait').show();
            var requests_left = target.count();
            for (var i = 0; i < target.count(); i++) {
                $.post({
                    url: '/api/v1/admin/pv_stats/permission/' + target.data()[i].id,
                    dataType: 'json',
                    contentType: 'application/json',
                    data: JSON.stringify({allow: new_status})},
                    (data, status, xhr) => {
                        g_pv_stats_permissions_table.row("#" + data.data[0].id).data(data.data[0]).draw();
                    })
                .fail((xhr, status, error) => {
                    modal("Set request status failure", xhr.responseText);
                })
                .always(() => {
                    requests_left--;
                    if (!requests_left) {
                        $('.wait').hide();
                    }
                });
            }
        }
    });
}
