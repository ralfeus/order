var NO_SHIPPING_ID = 4;

function round_up(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}