(function() { // Isolating variables scope

var g_roles = [];

$.fn.dataTable.ext.buttons.disable = {
    extend: 'selected',
    action: function(e, dt, node, config) {
        change_user_status(dt.rows({selected: true}), false);
    }
};
$.fn.dataTable.ext.buttons.enable = {
    extend: 'selected',
    action: function(e, dt, node, config) {
        change_user_status(dt.rows({selected: true}), true);
    }
};

$(document).ready( function () {
    get_dictionaries()
        .then(init_table);
});

async function get_dictionaries() {
    g_roles = await get_list('/api/v1/admin/user/role');
}

function init_table() {
    var base_ajax = {
        contentType: 'application/json'
    };
    function normalize_and_stringify(input) {
        input.roles = input.roles.map(r => r.id);
        return JSON.stringify(input);
    }
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: $.extend(true, {}, base_ajax, {
                url: '/api/v1/admin/user',
                data: d => normalize_and_stringify(d.data[0])
            }),
            edit: $.extend(true, {}, base_ajax, {
                url: '/api/v1/admin/user/_id_',
                data: d => normalize_and_stringify(Object.entries(d.data)[0][1])
            }),
            remove: {
                type: 'DELETE',
                url: '/api/v1/admin/user/_id_'
            }
        },
        table: '#users',
        template: '#user-form',
        idSrc: 'id',
        fields: [
            {label: 'Username', name: 'username'},
            {label: 'Password', name: 'password', type: 'password'},
            {label: 'Confirm password', name: 'confirm', type: 'password'},
            {label: 'E-mail', name: 'email'},
            {label: 'Phone', name: 'phone'},
            {label: 'Atomy ID', name: 'atomy_id'},
            {
                label: "Roles",
                name: "roles[].id",
                type: "checkbox",
                options: g_roles.map(entry => ({
                    value: entry.id,
                    label: entry.name
                }))
            }        ]
    });

    $('#users').DataTable({
        dom: 'lfrBtip', 
        ajax: {
            url: '/api/v1/admin/user',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({'all': true}),
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor, text: 'Create'},
            {extend: 'edit', editor: editor, text: 'Edit'},
            {extend: 'remove', editor: editor, text: 'Delete'},
            {extend: 'enable', text: 'Enable'},
            {extend: 'disable', text: 'Disable'}
        ],
        columns: [
            {data: 'id'},
            {data: 'username'},
            {data: 'email'},
            {data: 'enabled'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        rowId: 'id',
        select: true
    });
}

function change_user_status(rows, status) {
    $('.wait').show();
    var users = rows.data().map(row => row.id).toArray();
    var to_do = users.length;
    users.forEach(user_id => {
        $.ajax({
            url: '/api/v1/admin/user/' + user_id,
            method: 'post',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({enabled: status}),
            complete: function() {
                to_do--;
                if (!to_do) {
                    $('.wait').hide();
                }
            },
            success: function(data) {
                rows.row("#" + data.data[0].id).data(data.data[0]).draw();
            }
        });
    });
}

})();