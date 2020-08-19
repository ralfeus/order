var urlXLSX = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/xlsx.js";
var urlJSZIP = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/jszip.js";

var order_product_number = 0;

$(document).ready(() => {
    $('#excel')
        .on('change', function() {
            $('.wait').show();
            read_file(this.files[0]);
        })
    $('.excel').show();
});

function read_file(file) {
    const reader = new FileReader();
    reader.onload = function(event) {
        load_excel(event.target.result)
    };
    reader.readAsBinaryString(file)
}

function load_excel(data) {
    cleanup();
    var wb;
    try {
        var wb = XLSX.read(data, { type: 'binary' });
    } catch (e) {
        alert("Some error: " + e);
    }
    var ws = wb.Sheets['Бланк'];
    var current_node;
    var item;

    var countries = {
        0: 'korea',
        1: 'ru',
        2: 'ua',
        3: 'in',
        4: 'au',
        5: 'br',
        6: 'ca',
        7: 'cn',
        8: 'fr',
        9: 'de',
        10: 'hk',
        11: 'id',
        12: 'jp',
        13: 'my',
        14: 'nz',
        15: 'ph',
        16: 'sg',
        17: 'es',
        18: 'tw',
        19: 'th',
        20: 'gb',
        21: 'us',
        22: 'vn',
        23: 'zone1',
        24: 'zone2',
        25: 'zone3',
        26: 'zone4',
        27: 'kazakhstan cargo'
    };

    $('#name').val(ws['B5'].v);
    $('#address').val(ws['B6'].v);
    $('#phone').val(ws['B7'].v);
    $('#shipping').val(countries[ws['L1'].v]);
    $('#country').val(countries[ws['L2'].v]);

    
    for (var i = 12; i <= 831; i++) {
        if (ws['A' + i] && /^\d+$/.test(ws['A' + i].v) && !ws['B' + i]) break;
        if (!ws['A' + i]) continue;
        // if (parseInt((i + 8) / 20) == (i + 8) / 20 && i != 32) {
        if (/^\d+$/.test(ws['A' + i].v) && /^\d+/.test(ws['B' + i].v) && !ws['E' + i]) {
            current_node = add_user(ws['B' + i].v);
            item = 0;
        } else {
            var quantity;
            if (ws['D' + i]) {
                quantity = parseInt(ws['D' + i].v);
            } else {
                quantity = 0;
            }
            if (isNaN(quantity)) {
                quantity = 0;
            }
            add_product(current_node, item, ws['A' + i].v, quantity);
            item++;
        }
    }
    alert('Order is prefilled. Submit it.');
}

function add_product(current_node, item, product_id, quantity) {
    if (item) {
        var button = $('input[id^=add_userItem]', current_node).attr('id');
        add_product_row(button);
    }
    var item_code_node = $('.item-code', current_node).last();
    item_code_node.val(product_id);
    $('.item-quantity', current_node).last().val(quantity);
    order_product_number++;
    product_line_fill(item_code_node[0])
        .then(() => {
            order_product_number--;
            if (!order_product_number) {
                $('.wait').hide();
            }
        });
}

function add_user(subcustomer) {
    var subcustomer_node = add_subcustomer();
    $('.subcustomer-identity', subcustomer_node).val(subcustomer);
    return subcustomer_node;
}

function cleanup() {
    clear_form();
    delete_subcustomer($('.btn-delete'));
}