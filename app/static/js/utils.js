var NO_SHIPPING_ID = 4;

function round_up(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}

function modal(title, text) {
    $('.modal-title').text(title);
    $('.modal-body').text(text);
    $('.modal').modal();
}

function format_date(date) {
    if (date.valueOf()) {
        d = [ date.getFullYear() ].concat([
            '0' + (date.getMonth() + 1),
            '0' + date.getDate(),
            '0' + date.getHours(),
            '0' + date.getMinutes()
        ].map(component => component.slice(-2))); // take last 2 digits of every component

        // join the components into date
        return d.slice(0, 3).join('-') + ' ' + d.slice(3).join(':');
    } else {
        return '';
    }
}

async function get_currencies() {
    return get_list('/api/v1/currency');
}

async function get_list(url) {
    return await fetch(url);
}

function get_payment_methods() {
    return get_list('/api/v1/payment/method');
}

async function get_users() {
    return get_list('/api/v1/user');
}

$(document).ready(function(){
    $('.dropdown-submenu>a').on("click", function(e){
      $(this).next('ul').toggle();
      e.stopPropagation();
      e.preventDefault();
    });
  });
