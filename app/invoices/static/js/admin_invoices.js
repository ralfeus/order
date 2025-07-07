var g_invoice_table;
var g_invoice_templates;

async function get_dictionaries() {
    g_invoice_templates = await get_list('/api/v1/admin/invoice/template');
}

$(document).ready(function () {
    get_dictionaries()
        .then(init_invoices_table);
});

function init_invoices_table() {
    var editor = new $.fn.dataTable.Editor({
        table: '#invoices',
        idSrc: 'id',
        fields: [
            { label: "Customer name", name: 'customer' },
            { label: "Export ID", name: "export_id" }
        ],
        ajax: {
            edit: {
                url: '/api/v1/admin/invoice/_id_',
                method: 'post',
                dataType: 'json',
                contentType: 'application/json',
                data: data => JSON.stringify(data.data[editor.ids()[0]])
            }
        }
    });

    g_invoice_table = $('#invoices').DataTable({
        dom: 'lrBtip',
        ajax: {
            url: '/api/v1/admin/invoice'
        },
        buttons: [
            {
                extend: 'selected',
                text: "Download",
                action: function (e, dt, _node, _config) {
                    get_excel(dt.rows({ selected: true }));
                }
            },
            { extend: 'edit', text: 'Edit', editor: editor }
        ],
        columns: [
            {
                "className": 'invoice-actions',
                "orderable": false,
                "data": null,
                // "defaultContent": ''
                "defaultContent": ' \
                    <button \
                        class="btn btn-sm btn-secondary btn-open" \
                        onclick="open_invoice(this);">Open</button>'
            },
            { data: 'id' },
            { data: 'customer', className: 'editable' },
            { name: 'orders', data: row => row.orders.join() },
            { name: 'shippings', data: row => row.shippings.join() },
            { name: 'total', data: row => `${row.currency_code} ${row.total}` },
            { data: 'when_created' },
            { data: 'when_changed' }
        ],
        order: [[6, 'desc']],
        select: true,
        serverSide: true,
        processing: true,
        initComplete: function () { init_search(this); }
    });
}

function get_excel(rows) {
    if (g_invoice_templates.length == 0) {
        modal("Can't download invoice", "There is no available invoice template");
        return false;
    }
    var options = g_invoice_templates.reduce((html, template) => 
        `${html}<option value="${template}">${template}</option>`, '');
    modal("Choose the invoice template", `
        <div class="form-group">
            <select class="form-control" name="template" value="${g_invoice_templates[0]}">
                ${options}
            </select>
        </div>`,
        'form')
        .then(form => {
            if (!form || !form.template) {
                return false;
            }
            $('.wait').show();
            if (rows.count() == 1) {
                window.open(`/api/v1/admin/invoice/${rows.data()[0].id}/excel?template=${form.template}`);
            } else {
                var invoices = '';
                for (var i = 0; i < rows.count(); i++) {
                    invoices += `invoices=${rows.data()[i].id}&`;
                }
                window.open(`/api/v1/admin/invoice/excel?${invoices}&template=${form.template}`);
            }
            $('.wait').hide();
        });
}

function open_invoice(target) {
    window.location = g_invoice_table.row($(target).parents('tr')).data().id;
}
