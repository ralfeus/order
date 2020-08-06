var urlXLSX = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/xlsx.js";
var urlJSZIP = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.8.0/jszip.js";

$.when($.getScript(urlXLSX), $.getScript(urlJSZIP))
    .then(function () {
        $('<input type="file" />')
            .on('change', function() {
                read_file(this.files[0]);
                this.remove();
            })
            .trigger('click');
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
    var wb = XLSX.read(data, { type: 'binary' });
    var ws = wb.Sheets['Бланк'];
    var user_id = 0;
    for (var i = 12; i <= 831; i++) {
        if (parseInt((i + 8) / 20) == (i + 8) / 20 && i != 32) {
            user_id = add_user(user_id, ws['B' + i].v);
        } else {
            if (typeof ws['A' + i] === 'undefined') {
                continue;
            } else {
                add_product(user_id, ws['A' + i].v, ws['D' + i].v);
            }
        }
    }
    alert(wb.Sheets);
}

function add_user(user_id, subcustomer) {

}

function cleanup() {
    delete_subcustomer($('.btn-delete'));
}