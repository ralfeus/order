var g_packers;

$(document).ready(async function () {
    await get_dictionaries();
    init_order_packers_table();
});

function init_order_packers_table() {
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            edit: {
                url: '/api/v1/admin/order/packer/_id_',
                contentType: 'application/json',
                data: data => {
                    data = Object.entries(data.data)[0][1];
                    return JSON.stringify(data);
                }
            }
        },
        table: '#order_packers',
        idSrc: 'id',
        fields: [
            {
                name: 'packer',
                label: 'Packer',
                type: 'select2',
                opts: {
                    tags: true,
                    createTag: (tag) => ({ id: tag.term, text: tag.term, newOption: true }),
                },
                options: g_packers
            }
        ]
    });

    $('#order_packers').DataTable({
        lengthChange: false,
        buttons: [
            'pageLength'
        ],
        ajax: {
            url: '/api/v1/admin/order/packer',
            dataSrc: 'data'
        },
        rowId: 'id',
        columns: [
            { name: 'id', data: 'id' },
            { data: 'packer', className: 'editable', orderable: false },
            { data: 'when_created', render: dt_render_local_time },
            { data: 'when_changed', render: dt_render_local_time }
        ],
        serverSide: true,
        processing: true,
        order: [[0, 'desc']],
        initComplete: function () {
            var table = this;
            this.api().buttons().container().appendTo('#order_packers_wrapper .col-sm-12:eq(0)');
        }
    });
    $('#order_packers').on('click', 'td.editable', function (e) {
        editor.inline(this, { buttons: 'Save', submit: "allIfChanged", drawType: 'none' });
    });
}


async function get_dictionaries() {
    g_packers = [''].concat((await get_list('/api/v1/admin/order/packer/packer')).data.map(p => p.name));
    g_filter_sources = {
        packer: g_packers
    };
}