var urlXLSX = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/xlsx.js";
var urlJSZIP = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/jszip.js";

var order_product_number = 0;

$(document).ready(() => {
    $('#excel')
        .on('change',  async function() {
            $('.wait').show();
            await g_dictionaries_loaded;
            read_file(this.files[0]);
            this.value = null;
        })
    $('.excel').show();
});

function read_file(file) {
    const reader = new FileReader();
    reader.onload = async function(event) {
        modals_off();
        await load_excel(event.target.result)
        modals_on();
    };
    reader.readAsBinaryString(file)
}

async function load_excel(data) {
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
    await update_shipping_methods(countries[ws['L2'].v], 0);

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

}

async function add_product(current_node, item, product_id, quantity) {
    if (item) {
        var button = $('input[id^=add_userItem]', current_node).attr('id');
        add_product_row(button);
    }
    var item_code_node = $('.item-code', current_node).last();
    item_code_node.val(product_id);
    $('input.item-quantity', current_node).last().val(quantity);
    order_product_number++;
    await get_product(item_code_node[0], true);

    order_product_number--;
    if (!order_product_number) {
        $('.wait').hide();
    }

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
        if (/^\d+$/.test(ws['A' + i].v) && ws['B' + i] && !ws['D' + i]) {
            current_node = add_subcustomer(ws['B' + i].v);
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
                modals_on();
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
    update_grand_subtotal();      
}