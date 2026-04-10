const shippingId = document.getElementById('shipping_id').value;
const currentSubtype = document.getElementById('current_subtype').value;
const select = document.getElementById('subtype-select');

async function loadSubtypes() {
    try {
        const res = await fetch(`/api/v1/admin/shipping/separate/shipment-types`);
        if (!res.ok) throw new Error('Failed to load subtypes');
        const types = await res.json();

        select.innerHTML = '<option value="">— none —</option>';
        types.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.code;
            opt.textContent = `${t.name} (${t.code})`;
            if (t.code === currentSubtype) opt.selected = true;
            select.appendChild(opt);
        });
    } catch (err) {
        select.innerHTML = '<option value="">— could not load subtypes —</option>';
        console.error(err);
    }
}

document.getElementById('separate-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    try {
        const res = await fetch(`/api/v1/admin/shipping/separate/${shippingId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ subtype_code: select.value || null }),
        });
        if (!res.ok) throw new Error('Save failed');
        window.location.href = '/admin/shipping/';
    } catch (err) {
        alert('Error saving: ' + err.message);
    }
});

document.getElementById('cancel-btn').addEventListener('click', () => {
    window.location.href = '/admin/shipping/';
});

loadSubtypes();
