(function() {
let g_shipping_id;

$(document).ready(function() {
    g_shipping_id = $('#shipping_id').val();
    $('#submit').on('click', submit_changes);
});

function submit_changes(_sender) {
    $('.wait').show();
    $.ajax({
        url: `/api/v1/admin/shipping/fedex/${g_shipping_id}`,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            service_type: $('#service_type').val(),
        }),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data, _status, _xhr) {
            if (data.status === 'success') {
                modal('Success!', "The settings were saved");
            } else if (data.status === 'error') {
                if (data.message) {
                    modal('Something went wrong...', data.message);
                } else {
                    modal('Failure', "Unknown error has occurred. Contact administrator");
                }
            }
        },
        error: xhr => {
            var message;
            if (xhr.status == 500) {
                message = "Unknown error has occurred. Contact administrator"
            } else {
                message = xhr.responseText;
            }
            modal('Failure!', message);
        }
    });
}
})();