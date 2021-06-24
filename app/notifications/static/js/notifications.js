document.onreadystatechange = function() {
    if (document.readyState == 'complete') {
        $('#notifications_badge').on('click', () => {
            $.ajax('/api/v1/notification')
            .done(data => {
                data.forEach(notification => {
                    var toast = $('#toast-template').clone();
                    $('.toast-title', toast).html(notification.short_desc);
                    $('.toast-time', toast).html(
                        relativize_time(new Date(notification.when_created)));
                    $('.toast-body', toast).html(notification.long_desc);
                    $("#toast-container").append(toast);
                    toast.on('hidden.bs.toast', () => {
                        $.ajax({
                            url: '/api/v1/notification/' + notification.id + '?action=mark_read',
                            method: 'put'
                        });
                    })
                    toast.addClass('toast').show().toast('show');
                });
                $('#notifications_badge').hide();
            });
        });
    }
};