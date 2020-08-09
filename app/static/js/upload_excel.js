var urlXLSX = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/xlsx.js";
var urlJSZIP = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/jszip.js";

var order_product_number = 0;

$.when($.getScript(urlXLSX), $.getScript(urlJSZIP))
    .then(function () {
        $('<input type="file" />')
            .on('change', function() {
                read_file(this.files[0]);
                this.remove();
            })
            .trigger('click');
            $('.wait').show();
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
    } catch (Exception) {
        alert("Some error");
    }
    var ws = wb.Sheets['Бланк'];
    var current_node;
    var item;

    var countries = {
        0: 'korea',
        1: 'russia',
        2: 'ukraine',
        3: 'india',
        4: 'australia',
        5: 'brazil',
        6: 'canada',
        7: 'china',
        8: 'france',
        9: 'germany',
        10: 'hongkong',
        11: 'indonesia',
        12: 'japan',
        13: 'malaysia',
        14: 'newzeland',
        15: 'philippines',
        16: 'singapore',
        17: 'spain',
        18: 'taiwan',
        19: 'thailand',
        20: 'uk',
        21: 'us',
        22: 'vietnam',
        23: 'zone1',
        24: 'zone2',
        25: 'zone3',
        26: 'zone4',
        27: 'kazakhstan cargo'
    };

    $('#name').val(ws['B5'].v);
    $('#address').val(ws['B6'].v);
    $('#phone').val(ws['B7'].v);
    $('#country').val(countries[ws['J2'].v]);

    
    for (var i = 12; i <= 831; i++) {
        if (parseInt((i + 8) / 20) == (i + 8) / 20 && i != 32) {
            if (typeof ws['B' + i] === 'undefined') {
                break;
            }
            current_node = add_user(ws['B' + i].v);
            item = 0;
        } else {
            if (typeof ws['A' + i] === 'undefined') {
                continue;
            } else {
                add_product(current_node, item, ws['A' + i].v, ws['D' + i].v);
                item++;
            }
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
    fetch('/api/v1/product/' + product_id)
        .then(response => response.json())
        .then(data => {
            product_select(item_code_node, {
                'value': data[0].id,
                'label': data[0].name_english + " | " + data[0].name_russian,
                'price': data[0].price,
                'points': data[0].points,
                'weight': data[0].weight
            });
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
    delete_subcustomer($('.btn-delete'));
}