var urlXLSX = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/xlsx.js";
var urlJSZIP = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/jszip.js";

var order_product_number = 0;

$(document).ready(() => {
    g_dictionaries_loaded.then(() => {
        $('#excel')
            .on('change', function() {
                $('.wait').show();
                read_file(this.files[0]);
            })
        $('.excel').show();
    });
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
        27: 'kz', // Cargo,
        28: 'uz', // Cargo
        29: 'kz' // Russia ????
    };

    $('#name').val(ws['B5'].v);
    $('#address').val(ws['B6'].v);
    $('#phone').val(ws['B7'].v);
    $('#country').val(countries[ws['L2'].v]);
    get_shipping_methods(countries[ws['L2'].v], 0)
        .then(() => {
            if (ws['L2'].v == 0) {
                $('#shipping').val(4); // No shipping
            } else {
                // console.log("Country: ", $('#country').val());
                // console.log("L1: ", ws['L1'].v);
                // console.log("Shipping before: ", $('#shipping').val());
                // console.log("Shipping methods:", $('#shipping')[0].options)
                if (ws['L2'].v == 27) {
                    $('#shipping').val(3);
                } else if (ws['L2'].v == 28) {
                    $('#shipping').val(3);
                } else {
                    $('#shipping').val(ws['L1'].v);
                }
                // console.log("Shipping after:", $('#shipping').val());
            }
            load_products(ws);
        });
    // alert('Order is prefilled. Submit it.');
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
    get_product(item_code_node[0])
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

function load_products(ws) {
    for (var i = 12; i <= 2000; i++) {
        // Line is beginning of a new subcustomer but no subcustomer data provided
        // it means no new entries in the file
        if (ws['A' + i] && /^\d+$/.test(ws['A' + i].v) && !ws['B' + i]) break;
        // Just empty line. Ignored
        if (!ws['A' + i]) continue;
        // The line is beginning of new subcustomer
        if (/^\d+$/.test(ws['A' + i].v) && ws['B' + i] && !ws['E' + i]) {
            current_node = add_user(ws['B' + i].v);
            $('.subcustomer-seq-num', current_node).val(ws['A' + i].v);
            item = 0;
        // The line is product line
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
            if (typeof current_node === "undefined") {
                modal("Load order", 
                    "Couldn't load order from the Excel spreadsheet. " +
                    "No first subcustomer was identified");
                $('.wait').hide();
                return null;
            }
            add_product(current_node, item, ws['A' + i].v, quantity);
            item++;
        }
    }            
}