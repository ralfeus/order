(function() { // Isolating variables scope

var g_filter_sources = {
    'available': [{id: 1, text: 'true'}, {id: 0, text: 'false'}],
    'purchase': [{id: 1, text: 'true'}, {id: 0, text: 'false'}]
};
var g_shipping_methods;
var NO_IMAGE = '/static/images/no_image.jpg';
var IMAGE_MAX_SIZE = 5 * 1024 * 1024;
// Picture change requested in the editor: null - no change,
// File - upload new picture, false - remove picture
var g_image_change = null;

$(document).ready(function() {
    get_dictionaries()
    .then(init_table);
});

function delete_product(rows) {
    rows.every(function() {
        var row = this
        $.ajax({
            url: '/api/v1/admin/product/' + row.data().id,
            method: 'delete',
            success: function() {
                row.remove().draw();
            },
            error: function(xhr, _status, _error) {
                alert(xhr.responseJSON.message);
            }
        });
    });
}

async function get_dictionaries() {
    g_shipping_methods = await get_list('/api/v1/admin/shipping');
}

// Formatting function for row details
function format ( d ) {
    var product_details = $('.product-details')
    .clone()
    .show();
    $('#name', product_details).val(d.name);
    $('#name_english', product_details).val(d.name_english);
    $('#name_russian', product_details).val(d.name_russian);
    $('#weight', product_details).val(d.weight);
    $('#price', product_details).val(d.price);
    $('#points', product_details).val(d.points);
    if (d.separate_shipping) {
        $('#separate-shipping', product_details)[0].checked = true;
        $('#separate-shipping', product_details).parent().addClass('active');
        $('#separate-shipping', product_details)[0].nextSibling.textContent = 'Ships separately';
    }
    $('#separate-shipping', product_details).on('click', event => {
        event.target.nextSibling.textContent = event.target.checked 
            ? 'Ships separately' 
            : 'Ships in package';
    });
    
    if (d.available) {
        $('#available', product_details)[0].checked = true;
        $('#available', product_details).parent().addClass('active');
        $('#available', product_details)[0].nextSibling.textContent = 'Available';
    }
    $('#available', product_details).on('click', event => {
        event.target.nextSibling.textContent = event.target.checked ? 'Available' : 'Unavailable';
    });

    return product_details;

}

function init_image_field(editor) {
    g_image_change = null;
    var row = editor.mode() === 'edit' ? table_row_data(editor) : null;
    var image = row ? row.image : NO_IMAGE;
    $('#image-preview').attr('src', image);
    $('#image-remove').toggle(image !== NO_IMAGE);
    $('#image-file')
        .val('')
        .off('change')
        .on('change', event => {
            var file = event.target.files[0];
            if (!file) {
                return;
            }
            if (file.size > IMAGE_MAX_SIZE) {
                modal("Product picture", "Picture must not exceed 5 MB");
                event.target.value = '';
                return;
            }
            g_image_change = file;
            $('#image-preview').attr('src', URL.createObjectURL(file));
            $('#image-remove').show();
        });
    $('#image-remove')
        .off('click')
        .on('click', () => {
            g_image_change = false;
            $('#image-file').val('');
            $('#image-preview').attr('src', NO_IMAGE);
            $('#image-remove').hide();
        });
}

function table_row_data(editor) {
    var rows = $('#products').DataTable().rows(editor.modifier()).data();
    return rows.length === 1 ? rows[0] : null;
}

function save_image(product_id, product) {
    var change = g_image_change;
    g_image_change = null;
    var url = '/api/v1/admin/product/' + encodeURIComponent(product_id) + '/image';
    if (change === null) {
        return Promise.resolve(product);
    }
    if (change === false) {
        return Promise.resolve($.ajax({url: url, method: 'delete', dataType: 'json'}));
    }
    var form = new FormData();
    form.append('file', change);
    return Promise.resolve($.ajax({
        url: url,
        method: 'post',
        dataType: 'json',
        data: form,
        processData: false,
        contentType: false
    }));
}

function init_table() {
    var editor = new $.fn.dataTable.Editor({
        ajax: (_method, _url, data, success, error) => {
            var product_id = Object.entries(data.data)[0][0];
            var target = Object.entries(data.data)[0][1];
            var method = 'post';
            var url = '/api/v1/admin/product/' + product_id;
            if (data.action === 'create') {
                var url = '/api/v1/admin/product';
                product_id = target.id;
            } else if (data.action === 'remove') {
                method = 'delete';
            }
            target.available = target.available[0];
            target.synchronize = target.synchronize[0];
            target.purchase = target.purchase[0];
            target.shipping = target.shipping.map(s => s.id);
            $.ajax({
                url: url,
                method: method,
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify(target),
                success: data => {
                    save_image(product_id, data)
                        .then(data => success({data: [data]}))
                        .catch(xhr => {
                            modal("Product picture update error", xhr.responseText);
                            // Product itself is saved, so show it anyway
                            success({data: [data]});
                        });
                },
                error: (xhr, err, thrown) => {
                    modal(
                        "Product update error", 
                        xhr.responseJSON.message);
                    error(xhr, err, thrown);
                }
            });
        },
        table: '#products',
        template: '#product-form',
        idSrc: 'id',
        fields: [
            {label: 'Product ID', name: 'id'},
            {label: 'Name', name: 'name'},
            {label: 'Name english', name: 'name_english'},
            {label: 'Name russian', name: 'name_russian'},
            {label: 'Weight (g)', name: 'weight', def: 0},
            {label: 'Price', name: 'price', def: 0},
            {label: 'Points', name: 'points', def: 0},
            {
                label: 'Available', 
                name: 'available', 
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            },
            {
                label: 'Synchronize', 
                name: 'synchronize', 
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            },
            {
                label: 'Purchase', 
                name: 'purchase', 
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            },
            {
                label: "Color",
                name: 'color',
                type: 'colorpicker'
            },
            {
                label: "Shipping",
                name: "shipping[].id",
                type: "checkbox",
                options: g_shipping_methods.map(entry => ({
                    value: entry.id,
                    label: entry.name
                }))
            }
        ]
    });
    editor.on('open', () => {
        if (editor.field('id').val()) {
            editor.field('id').disable();
        } else {
            editor.field('id').enable();
        }
        init_image_field(editor);
        $('#color-text').on('change', () => {
            editor.field('color').val($('#color-text').val());
        })
        .val(editor.field('color').val());
    });
    editor.field('color').input().on('change', () => {
        $('#color-text').val(editor.field('color').val());
    });
    var table = $('#products').DataTable({
        dom: 'lrBtip', 
        ajax: {
            url: '/api/v1/admin/product',
            dataType: 'json',
            contentType: 'application/json'
        },
        buttons: [
            {extend: 'create', editor: editor, text: "Create"},
            {extend: 'edit', editor: editor, text: "Edit"},
            {extend: 'remove', editor: editor, text: "Delete"}
        ],
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {name: 'id', data: 'id'},
            {data: 'name'},
            {data: 'name_english'},
            {data: 'weight'},
            {data: 'price'},
            {data: 'points'},
            {data: 'available'},
            {data: 'purchase'}
        ],
        select: true,
        serverSide: true,
        processing: true,
        createdRow: (row, data) => {
            if (!data.available) {
                $(row).addClass('red-line');
            }
        },
        initComplete: function() { 
            var table = this;
            init_search(table, g_filter_sources)
            .then(() => init_table_filter(table)); 
        }
    });

    $('#products tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            $('tr.shown').each(function() {
                table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            row.child( format(row.data()) ).show();
            tr.addClass('shown');
            $('.btn-save').on('click', function() {
                var product_node = $(this).closest('.product-details');
                var data = {
                    id: row.data().id,
                    name: $('#name', product_node).val(),
                    name_english: $('#name_english', product_node).val(),
                    name_russian: $('#name_russian', product_node).val(),
                    points: $('#points', product_node).val(),
                    separate_shipping: $('#separate-shipping', product_node).is(':checked'),
                    price: $('#price', product_node).val(),
                    weight: $('#weight', product_node).val(),
                    available: $('#available', product_node).is(':checked')
                };
                $('.wait').show();
                $.ajax({
                    url: '/api/v1/admin/product',
                    method: 'post',
                    dataType: 'json',
                    contentType: 'application/json',
                    data: JSON.stringify(data),
                    complete: function() {
                        $('.wait').hide();
                    },
                    success: function() {
                        row.data(data).draw();
                    }
                })
            })
        }
    } );
}

})();