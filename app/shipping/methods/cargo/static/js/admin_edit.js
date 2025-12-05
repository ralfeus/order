$(document).ready(() => {
    const shippingId = $('#shipping_id').val();
    let selectedCountries = new Set();

    // Load countries and render checkboxes
    loadCountries();

    function loadCountries() {
        $.ajax({
            url: `/api/v1/admin/shipping/cargo/${shippingId}/countries`,
            method: 'GET',
            success: function(response) {
                renderCountries(response);
            },
            error: function(xhr) {
                alert('Error loading countries: ' + xhr.responseJSON.error);
            }
        });
    }

    function renderCountries(data) {
        const container = $('#countries-container');
        container.empty();

        // Group countries into columns (4 columns for full width usage)
        const countries = data.data;
        const numColumns = 4;
        const countriesPerColumn = Math.ceil(countries.length / numColumns);

        for (let col = 0; col < numColumns; col++) {
            const columnDiv = $('<div class="col-lg-3 col-md-6 col-sm-12"></div>');
            const startIndex = col * countriesPerColumn;
            const endIndex = Math.min(startIndex + countriesPerColumn, countries.length);

            for (let i = startIndex; i < endIndex; i++) {
                const country = countries[i];
                const checked = country.selected ? 'checked' : '';
                const checkboxHtml = `
                    <div class="form-check">
                        <input class="form-check-input country-checkbox" type="checkbox"
                               id="country-${country.id}" data-country-id="${country.id}" ${checked}>
                        <label class="form-check-label" for="country-${country.id}">
                            ${country.name}
                        </label>
                    </div>
                `;
                columnDiv.append(checkboxHtml);

                if (country.selected) {
                    selectedCountries.add(country.id);
                }
            }

            container.append(columnDiv);
        }
    }

    // Handle checkbox changes
    $(document).on('change', '.country-checkbox', function() {
        const countryId = $(this).data('country-id');
        if (this.checked) {
            selectedCountries.add(countryId);
        } else {
            selectedCountries.delete(countryId);
        }
    });

    // Handle form submission
    $('#countries-form').on('submit', function(e) {
        e.preventDefault();
        saveSelections();
    });

    // Handle cancel button
    $('#cancel-btn').on('click', function() {
        window.location.href = '/admin/shipping';
    });

    function saveSelections() {
        $.ajax({
            url: `/api/v1/admin/shipping/cargo/${shippingId}/countries`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                selected_countries: Array.from(selectedCountries)
            }),
            success: function(response) {
                alert('Countries saved successfully!');
            },
            error: function(xhr) {
                alert('Error saving countries: ' + xhr.responseJSON.error);
            }
        });
    }
});
