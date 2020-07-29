$.fn.dataTable.ext.buttons.create = {
    action: function(e, dt, node, config) {
        window.location = '/admin/user/new';
    }
};
$.fn.dataTable.ext.buttons.disable = {
    action: function(e, dt, node, config) {
        window.location = '/admin/users';
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
            // {extend: 'delete', text: 'Delete'},
            {extend: 'disable', text: 'Disable'}
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
                    user_name: $('#user_name', users_node).val(),
                    email: $('#email', users_node).val(),
                    password: $('#password', users_node).val(),
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/v1/admin/user/' + row.data().id,
                    method: 'post',
                    dataType: 'json',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    complete: function() {
                        $('.wait').hide();
                    },
                    success: function() {
                        row.data(data).draw();
                    }
                })
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