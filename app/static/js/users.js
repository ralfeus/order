$.fn.dataTable.ext.buttons.create = {
    action: function(e, dt, node, config) {
        window.location = '/admin/user/new';
    }
};
$.fn.dataTable.ext.buttons.disable = {
    action: function(e, dt, node, config) {
        change_user_status(dt.rows({selected: true}), false);
    }
};
$.fn.dataTable.ext.buttons.enable = {
    action: function(e, dt, node, config) {
        change_user_status(dt.rows({selected: true}), true);
    }
};
// $.fn.dataTable.ext.buttons.delete = {
//     action: function(e, dt, node, config) {
//         delete_user(dt.rows({selected: true}));
//     }
// }

$(document).ready( function () {
    var table = $('#users').DataTable({
        dom: 'lfrBtip', 
        ajax: {
            url: '/api/user',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({'all': true}),
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', text: 'Create'},
            {extend: 'enable', text: 'Enable'},
            {extend: 'disable', text: 'Disable'},
            // {extend: 'delete', text: 'Delete'}
        ],
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'id'},
            {data: 'username'},
            {data: 'email'},
            {data: 'enabled'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        select: true
    });

    $('#users tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // Open this row
            row.child( format(row.data()) ).show();
            tr.addClass('shown');
            $('.btn-save').on('click', function() {
                var users_node = $(this).closest('.user-details');
                var data = {
                    username: $('#username', users_node).val(),
                    email: $('#email', users_node).val(),
                    password: $('#password', users_node).val(),
                    enabled: $('#enabled', users_node).val()
                };
                update_user(row, data);
            })
        }
    } );
});

// Formatting function for row details
function format ( d ) {
    // `d` is the original data object for the row
    return '' +
        '<div class="container-fluid user-details">'+
            '<div class="col-6">' +
                '<label for="username">User name:</label>'+
                '<input id="username" class="form-control col-5" value="'+ d.username +'"/>'+
                '<label for="email">Email:</label>' +
                '<input id="email" class="form-control col-1" value="' + d.email + '"/>' +
                '<label class="col-1" for="password">Password:</label>'+
                '<input id="password" class="form-control col-5" value="' + d.password + '"/>'+
            '</div>' +
            '<div class="col-2">' +
                '<input type="button" class="button btn-primary btn-save col-2" value="Save" />' +
            '</div>' +
        '</div>';
}

function delete_user(rows) {
    rows.every(function() {
        var row = this
        $.ajax({
            url: '/api/user/' + row.data().id,
            method: 'delete',
            success: function() {
                row.remove().draw()
            },
            error: function(xhr, _status, _error) {
                alert(xhr.responseJSON.message);
            }
        });
    });
}

function update_user(row, update_data) {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/admin/user/' + row.data().id,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify(update_data),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data) {
            row.data(data).draw();
        }
    })
}

function change_user_status(rows, status) {
    $('.wait').show();
    var to_do = rows.length;
    for (var i = 0; i < rows.length; i++) {
        $.ajax({
            url: '/api/v1/admin/user/' + rows.data()[i].id,
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
                rows.data(data).draw();
            }
        });
    }
}