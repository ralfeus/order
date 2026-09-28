/*
 * End-user product catalog.
 * Delivery cost of a product is its share (by weight) of a 10kg EMS parcel
 * to the chosen country. All amounts come in base currency and are converted
 * to the user's currency the same way as on the new order page.
 */
var currencyRates = {};
var parcelRate = null; // EMS rate of 10kg parcel in base currency, null if unknown
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
    init_table(products);
    $('#catalog-country').on('change', country_changed);
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
    let rate = null;
    let error = null;
    if (EMS_SHIPPING_ID === null) {
        error = 'EMS delivery is not available. Delivery costs can\'t be estimated.';
    } else if (country) {
        try {
            const response = await fetch(
                `/api/v1/shipping/rate/${country}/${EMS_SHIPPING_ID}/${CATALOG_PARCEL_WEIGHT}`);
            if (response.ok) {
                rate = (await response.json()).shipping_cost;
            } else {
                error = `There is no EMS delivery to ${$('#catalog-country option:selected').text()}. ` +
                        'Delivery costs can\'t be estimated.';
            }
        } catch (e) {
            error = 'Couldn\'t get delivery rate. Try again later.';
        }
    }
    if (requestId != rateRequestId) return; // a newer country was selected meanwhile
    parcelRate = rate;
    show_alert(error);
    redraw();
}

async function country_changed() {
    catalogCountry = $('#catalog-country').val();
    save_preferences({ catalog_country: catalogCountry });
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
