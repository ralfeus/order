const stripe = Stripe(STRIPE_KEY);
const elements = stripe.elements({
    mode: 'payment',
    currency: CURRENCY,
    amount: Math.round(TOTAL_AMOUNT * 100),
    paymentMethodCreation: 'manual'
});
const paymentElement = elements.create('payment', { layout: 'tabs' });
paymentElement.mount('#payment-element');

let currentPaymentMethod = null;

// Step 1: Card submission
document.getElementById('card-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById('card-submit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Processing...';

    try {
        const { error: submitError } = await elements.submit();
        if (submitError) {
            showMessage(submitError.message, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Continue';
            return;
        }

        const { error, paymentMethod } = await stripe.createPaymentMethod({ elements, params: {} });
        if (error) {
            showMessage(error.message, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Continue';
            return;
        }

        currentPaymentMethod = paymentMethod;
        document.getElementById('confirm-amount').textContent =
            `EUR ${TOTAL_AMOUNT.toFixed(2)}`;
        document.getElementById('card-entry-section').classList.add('hidden');
        document.getElementById('confirmation-section').classList.remove('hidden');

    } catch (err) {
        showMessage('An error occurred: ' + err.message, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Continue';
    }
});

// Step 2: Confirm payment
document.getElementById('confirm-button').addEventListener('click', async () => {
    const confirmBtn = document.getElementById('confirm-button');
    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Processing...';

    try {
        const response = await fetch(`/api/v1/order/${ORDER_ID}/shipment/pay`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payment_method_id: currentPaymentMethod.id })
        });

        const { client_secret, error } = await response.json();
        if (error) {
            showMessage(error, 'error');
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Confirm Payment';
            return;
        }

        const { error: confirmError } = await stripe.confirmPayment({
            clientSecret: client_secret,
            confirmParams: {
                return_url: `${window.location.origin}/orders/${ORDER_ID}/shipment/pay/success`
            }
        });

        if (confirmError) {
            showMessage(confirmError.message, 'error');
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Confirm Payment';
        }

    } catch (err) {
        showMessage('Payment failed: ' + err.message, 'error');
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Confirm Payment';
    }
});

// Back button
document.getElementById('back-button').addEventListener('click', () => {
    document.getElementById('confirmation-section').classList.add('hidden');
    document.getElementById('card-entry-section').classList.remove('hidden');
    document.getElementById('card-submit').disabled = false;
    document.getElementById('card-submit').textContent = 'Continue';
});

function showMessage(text, type) {
    const el = document.getElementById('message');
    el.textContent = text;
    el.className = `message ${type}`;
    el.classList.remove('hidden');
}
