const stripe = Stripe(STRIPE_KEY);
const elements = stripe.elements({    
    mode: 'payment',
    currency: CURRENCY.toLowerCase(),
    amount: BASE_AMOUNT * 100, // The amount should be in minimal units (cents)
    paymentMethodCreation: 'manual'
});
const paymentElement = elements.create('payment', {
    layout: 'tabs',
});
paymentElement.mount('#payment-element');

let currentPaymentMethod = null;
let currentFees = null;

// Step 1: Detect card and calculate fees
document.getElementById('card-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = document.getElementById('card-submit');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Detecting card...';

    try {
        const {error: submitError} = await elements.submit();
        
        if (submitError) {
        showMessage(submitError.message, 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Continue';
        return;
        }        
        // Create payment method to detect card details
        const {error, paymentMethod} = await stripe.createPaymentMethod({
            elements,
            params: {}
        });

        if (error) {
            showMessage(error.message, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Continue';
            return;
        }

        currentPaymentMethod = paymentMethod;

        // Send to backend to calculate fees
        const response = await fetch('/api/v1/payment/stripe/detect-card', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                payment_method_id: paymentMethod.id,
                payment_id: PAYMENT_ID
            })
        });

        const data = await response.json();
        
        if (data.error) {
            showMessage(data.error, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Continue';
            return;
        }

        // Update UI with fees
        document.getElementById('service-fee-amount').textContent = 
            `${CURRENCY} ${data.fees.toFixed(2)}`;
        document.getElementById('service-fee-line').classList.remove('hidden');
        document.getElementById('total-amount').textContent = 
            `${CURRENCY} ${data.total_amount.toFixed(2)}`;

        // Show confirmation
        document.getElementById('card-type-display').textContent = data.fees.card_type;
        document.getElementById('confirm-amount').textContent = 
            `${CURRENCY} ${data.total_amount.toFixed(2)}`;
        
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
        // Create PaymentIntent on backend
        const response = await fetch('/api/v1/payment/stripe/create-payment-intent', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                payment_id: PAYMENT_ID,
                payment_method_id: currentPaymentMethod.id,
                fees: currentFees
            })
        });

        const {client_secret, payment_intent_id, error} = await response.json();
        
        if (error) {
            showMessage(error, 'error');
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Confirm Payment';
            return;
        }

        // Confirm payment with Stripe
        const {error: confirmError} = await stripe.confirmPayment({
            clientSecret: client_secret,
            confirmParams: {
                return_url: `${window.location.origin}/payments/${PAYMENT_ID}/stripe/success`,
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
    const messageEl = document.getElementById('message');
    messageEl.textContent = text;
    messageEl.className = `message ${type}`;
    messageEl.classList.remove('hidden');
}
