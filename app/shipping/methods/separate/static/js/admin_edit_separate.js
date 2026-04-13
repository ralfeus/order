const shippingId = document.getElementById('shipping_id').value;
const countryList = document.getElementById('country-list');

// Country codes currently enabled for this shipping method
let enabledCodes = new Set();

async function loadData() {
    try {
        const [allRes, enabledRes] = await Promise.all([
            fetch('/api/v1/country'),
            fetch(`/api/v1/admin/shipping/separate/${shippingId}/countries`),
        ]);
        if (!allRes.ok || !enabledRes.ok) throw new Error('Failed to load data');

        const allCountries = await allRes.json();   // [{id, name, ...}, ...]
        const enabledList  = await enabledRes.json(); // ['DE', 'FR', ...]
        enabledCodes = new Set(enabledList);

        renderCountries(allCountries);
    } catch (err) {
        countryList.innerHTML = '<span class="text-danger">Could not load countries.</span>';
        console.error(err);
    }
}

function renderCountries(countries) {
    // Sort by name
    const sorted = [...countries].sort((a, b) => a.name.localeCompare(b.name));

    // Search box
    const searchHtml = `
        <input type="text" id="country-search" class="form-control form-control-sm mb-2"
               placeholder="Search…" autocomplete="off">`;

    const items = sorted.map(c => `
        <div class="form-check country-item" data-name="${c.name.toLowerCase()}">
            <input class="form-check-input" type="checkbox" id="cc-${c.id}" value="${c.id}"
                   ${enabledCodes.has(c.id) ? 'checked' : ''}>
            <label class="form-check-label" for="cc-${c.id}">
                ${c.name} <span class="text-muted">(${c.id})</span>
            </label>
        </div>`).join('');

    countryList.innerHTML = searchHtml + items;

    document.getElementById('country-search').addEventListener('input', function () {
        const q = this.value.toLowerCase();
        document.querySelectorAll('.country-item').forEach(el => {
            el.style.display = el.dataset.name.includes(q) ? '' : 'none';
        });
    });
}

document.getElementById('separate-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const selected = Array.from(
        document.querySelectorAll('#country-list input[type=checkbox]:checked')
    ).map(cb => cb.value);

    try {
        const res = await fetch(`/api/v1/admin/shipping/separate/${shippingId}/countries`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ countries: selected }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error ?? 'Save failed');
        }
        window.location.href = '/admin/shipping/';
    } catch (err) {
        alert('Error saving: ' + err.message);
    }
});

document.getElementById('cancel-btn').addEventListener('click', () => {
    window.location.href = '/admin/shipping/';
});

loadData();
