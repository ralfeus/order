/*
 * End-user product catalog.
 * Delivery cost of a product is its share (by weight) of a 10kg parcel
 * sent by the chosen shipping method to the chosen country. All amounts come in base currency and are converted
 * to the user's currency the same way as on the new order page.
 */
var currencyRates = {};
var parcelRate = null; // rate of 10kg parcel in base currency, null if unknown
var rateUnavailable = null; // reason why the rate is unknown, shown as a tooltip
var rateRequestId = 0;
var catalogTable;

$(document).ready(async () => {
    const [currencies, countries, products] = await Promise.all([
        get_currencies(),
        get_list('/api/v1/country'),
        get_list('/api/v1/product/catalog')
    ]);
    for (const currency of currencies) {
        currencyRates[currency.code] = currency.rate;
    }
    init_country_select(countries);
    init_shipping_select();
    init_table(products);
    $('#catalog-country').on('change', country_changed);
    $('#catalog-shipping').on('change', shipping_changed);
    $('#catalog-markup').on('change', markup_changed);
    await update_parcel_rate();
});

function init_country_select(countries) {
    const select = $('#catalog-country');
    select.html(countries.map(c =>
        `<option value="${escape_html(c.id)}">${escape_html(c.name)}</option>`));
    if (countries.some(c => c.id == catalogCountry)) {
        select.val(catalogCountry);
    } else {
        catalogCountry = select.val();
    }
    select.prop('disabled', false);
}

/**
 * Preselects the saved shipping method if it's still available,
 * otherwise EMS, otherwise the first one
 */
function init_shipping_select() {
    const select = $('#catalog-shipping');
    select.html(SHIPPING_METHODS.map(s =>
        `<option value="${escape_html(s.id)}">${escape_html(s.name)}</option>`));
    const ids = SHIPPING_METHODS.map(s => s.id);
    if (!ids.includes(catalogShipping)) {
        catalogShipping = ids.includes(EMS_SHIPPING_ID) ? EMS_SHIPPING_ID : (ids[0] ?? null);
    }
    select.val(catalogShipping);
    select.prop('disabled', SHIPPING_METHODS.length == 0);
}

function init_table(products) {
    const money = (field) => ({
        data: null,
        className: 'money money-' + field,
        render: (product, type) => render_money(calc_prices(product)[field], type)
    });
    catalogTable = $('#catalog').DataTable({
        data: products,
        pageLength: 50,
        order: [[0, 'asc']],
        columns: [
            {
                data: null,
                render: (product, type) => {
                    if (type == 'sort') return product.name;
                    if (type != 'display') return product.id + ' ' + product.name;
                    return `<div class="product-cell">
                        <img class="product-thumb" src="${escape_html(product.image)}"
                             alt="" loading="lazy" />
                        <div>
                            <div class="product-name">${escape_html(product.name)}</div>
                            <div class="product-id">#${escape_html(product.id)}</div>
                        </div>
                    </div>`;
                }
            },
            money('price'),
            {
                ...money('delivery'),
                render: (product, type) => {
                    if (type == 'display' && parcelRate !== null && !product.weight) {
                        return '<span class="text-muted" title="Weight unknown">—</span>';
                    }
                    if (type == 'display' && parcelRate === null && rateUnavailable) {
                        return `<span class="text-muted" title="${escape_html(rateUnavailable)}">n/a</span>`;
                    }
                    return render_money(calc_prices(product).delivery, type);
                }
            },
            money('total'),
            money('recommended')
        ],
        language: { emptyTable: 'No products available' }
    });
}

/**
 * Calculates product prices in base currency.
 * delivery, total and recommended are null if no parcel rate is known
 */
function calc_prices(product) {
    const price = product.price || 0;
    if (parcelRate === null) {
        return { price: price, delivery: null, total: null, recommended: null };
    }
    const delivery = parcelRate * (product.weight || 0) / CATALOG_PARCEL_WEIGHT;
    const total = price + delivery;
    return {
        price: price,
        delivery: delivery,
        total: total,
        recommended: total * catalogMarkup
    };
}

function render_money(amount_base, type) {
    if (amount_base === null) {
        return type == 'display' ? '<span class="text-muted">n/a</span>' : -1;
    }
    const rate = currencyRates[USER_CURRENCY_CODE];
    if (!USER_CURRENCY_CODE || !rate) {
        return type == 'display' ? fmtCurr(base_country).format(round_up(amount_base, 0)) : amount_base;
    }
    const amount = round_up(amount_base * rate, 2);
    if (type != 'display') return amount;
    return new Intl.NumberFormat(undefined,
        { style: 'currency', currency: USER_CURRENCY_CODE }).format(amount);
}

async function update_parcel_rate() {
    const requestId = ++rateRequestId;
    const country = catalogCountry;
    const shipping = catalogShipping;
    let rate = null;
    let error = null;
    let unavailable = null;
    if (shipping === null) {
        error = 'No shipping methods are available. Delivery costs can\'t be estimated.';
    } else if (country) {
        try {
            const response = await fetch(
                `/api/v1/shipping/rate/${country}/${shipping}/${CATALOG_PARCEL_WEIGHT}`);
            if (response.ok) {
                rate = (await response.json()).shipping_cost;
            } else {
                const shippingName = $('#catalog-shipping option:selected').text();
                const countryName = $('#catalog-country option:selected').text();
                unavailable = `${shippingName} doesn't deliver to ${countryName}`;
                error = `There is no ${shippingName} delivery to ${countryName}. ` +
                        'Delivery costs can\'t be estimated.';
            }
        } catch (e) {
            error = 'Couldn\'t get delivery rate. Try again later.';
        }
    }
    // a newer country or shipping method was selected meanwhile
    if (requestId != rateRequestId) return;
    parcelRate = rate;
    rateUnavailable = unavailable;
    show_alert(error);
    redraw();
}

async function country_changed() {
    catalogCountry = $('#catalog-country').val();
    save_preferences({ catalog_country: catalogCountry });
    await update_parcel_rate();
}

async function shipping_changed() {
    catalogShipping = parseInt($('#catalog-shipping').val());
    save_preferences({ catalog_shipping: catalogShipping });
    await update_parcel_rate();
}

function markup_changed() {
    const input = $('#catalog-markup');
    const markup = parseFloat(input.val());
    if (!isFinite(markup) || markup <= 0) {
        input.addClass('is-invalid');
        return;
    }
    input.removeClass('is-invalid');
    catalogMarkup = markup;
    save_preferences({ catalog_markup: markup });
    redraw();
}

async function save_preferences(preferences) {
    try {
        const response = await fetch('/api/v1/user/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(preferences)
        });
        if (!response.ok) {
            console.warn('Couldn\'t save catalog preferences', await response.text());
        }
    } catch (e) {
        console.warn('Couldn\'t save catalog preferences', e);
    }
}

function redraw() {
    catalogTable.rows().invalidate().draw(false);
}

function show_alert(message) {
    $('#catalog-alert').text(message || '').toggleClass('d-none', !message);
}

function escape_html(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
