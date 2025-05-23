$(document).ready(function () {
    $("#signupForm").submit(function (event) {
        event.preventDefault();

        var formData = {
            username: $("#username").val(),
            password: $("#password").val(),
            confirm: $("#confirm").val(),
            email: $("#email").val(),
            phone: $("#phone").val(),
            atomy_id: $("#atomy_id").val()
        };
        $('.invalid-feedback').remove(); // Remove existing error messages
        $('.is-invalid').removeClass('is-invalid'); // Remove invalid class from all fields
        $('#signupError').hide(); // Hide the signup error message
        $.ajax({
            type: "POST",
            url: "/api/v1/user/signup", // Replace with your actual signup endpoint
            data: JSON.stringify(formData),
            contentType: "application/json; charset=utf-8",
            dataType: "json",
            success: function (data) {
                if (data.error) {
                    $("#signupError").text(data.error).show();
                } else {
                    window.location.href = '/';
                }
            },
            error: function (error) {
                var errorData = error.responseJSON;
                if (errorData.fieldErrors) {
                    errorData.fieldErrors.forEach(function (fieldError) {
                        // Display the error message next to the corresponding field
                        var field = $(`#${fieldError.name}`);
                        field.addClass("is-invalid");
                        field.after(`<div class="invalid-feedback">${fieldError.status}</div>`);
                    });
                }
                $("#signupError").text(`Sign up failed: ${errorData.error}`).show();
            }
        });
    });
});
