var g_rates_table;

function normalize_and_stringify(input) {
    target = Object.entries(input)[0][1];
    return JSON.stringify(target)
}

$(document).ready(() => {
    var editor;
    editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: `/api/v1/admin/shipping/weight_based/${$('#shipping_id').val()}/rate`,
                contentType: 'application/json',
                data: data => normalize_and_stringify(data.data)
            },
            edit: {
                url: `/api/v1/admin/shipping/weight_based/${$('#shipping_id').val()}/rate`,
                contentType: 'application/json',
                data: data => normalize_and_stringify(data.data)
            },
            remove: {
                url: `/api/v1/admin/shipping/weight_based/${$('#shipping_id').val()}/rate/_id_`,
                method: 'delete'
            },
        },
        table: '#rates',
        idSrc: 'id',
        fields: [
            {label: 'Destination', name: 'destination'},
            {label: 'Minimum weight', name: 'minimum_weight'},
            {label: 'Maximum weight', name: 'maximum_weight'},
            {label: 'Weight step', name: 'weight_step'},
            {label: 'Cost per kg', name: 'cost_per_kg'}
        ]
    });
    $('#rates').on( 'click', 'td', function (e) {
        editor.inline(this, { onBlur: 'submit', drawType: 'none'});
    }); 
    g_shipping_methods_table = $('#rates').DataTable({
        dom: 'Btp',
        ajax: {
            url: `/api/v1/admin/shipping/weight_based/${$('#shipping_id').val()}/rate`,
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor},
            {extend: 'remove', editor: editor}
        ],
        columns: [
            {data: 'destination'},
            {data: 'minimum_weight'},
            {data: 'maximum_weight'},
            {data: 'weight_step'},
            {data: 'cost_per_kg'}
        ],
        select: true
    });
});