var currencies = [];

$.fn.dataTable.ext.buttons.create = {
    action: function(_e, _dt, _node, _config) {
        window.location = '/wallet/new';
    }
};
$.fn.dataTable.ext.buttons.status = {
    action: function(_e, dt, _node, _config) {
        setStatus(dt.rows({selected: true}), this.text());
    }
};

$(document).ready( function () {
    get_currencies();
    var table = $('#transactions').DataTable({
        dom: 'lfrBtip',
        buttons: [
            { extend: 'create', text: 'Create new transaction' },
            { 
                extend: 'collection', 
                text: 'Set status',
                buttons: [
                    { extend: 'status', text: 'Approved' },
                    { extend: 'status', text: 'Rejected'}
                ]
            }
        ],        
        ajax: {
            url: '/api/v1/admin/transaction',
            dataSrc: ''
        },
        columns: [
            {
                "className":      'details-control',
                "orderable":      false,
                "data":           null,
                "defaultContent": ''
            },
            {data: 'id'},
            {data: 'user_name'},
            {data: 'amount_original_string'},
            {data: 'amount_krw'},
            {data: 'amount_received_krw'},
            {data: 'status'},
            {data: 'when_created'},
            {data: 'when_changed'}
        ],
        select: true,
        footerCallback: function(row, data, start, end, display) {
            var api = this.api(), data;
 
            // // Remove the formatting to get integer data for summation
            // var intVal = function ( i ) {
            //     return typeof i === 'string' ?
            //         i.replace(/[\$,]/g, '')*1 :
            //         typeof i === 'number' ?
            //             i : 0;
            // };
 
            // Total over all pages
            totalSentOriginal = api
                .data()
                .reduce(function (accumulator, current) {
                    if (!accumulator[current.currency_code]) { 
                        accumulator[current.currency_code] = 0;
                    }
                    accumulator[current.currency_code] += current.amount_original;
                    return accumulator;
                }, {})
            totalSentOriginalString = Object.entries(totalSentOriginal)
                .map(e => e[0] + ": " + e[1].toLocaleString() + "<br />");
            totalSentKRW = api
                .column( 4 )
                .data()
                .reduce( function (a, b) {
                    return a + b;
                }, 0 );
            totalReceivedKRW = api
                .column( 5 )
                .data()
                .reduce( function (a, b) {
                    return a + b;
                }, 0 );
 
            // Update footer
            $(api.column(3).footer()).html(totalSentOriginalString);
            $( api.column(4).footer() ).html('₩' + totalSentKRW.toLocaleString());        
            $( api.column(5).footer() ).html('₩' + totalReceivedKRW.toLocaleString());        
        }
    });

    // table.on('select', function(e, dt, type, indexes) {
    //         // Total over all pages
    //         totalSentOriginal = dt.data()
    //             .reduce(function (accumulator, i) {
    //                 if (!accumulator[i.currency_code]) { 
    //                     accumulator[dt.data()[i].currency_code] = 0;
    //                 }
    //                 accumulator[dt.data()[i].currency_code] += dt.data()[i].amount_original;
    //                 return accumulator;
    //             }, {})
    //         totalSentOriginalString = Object.entries(totalSentOriginal)
    //             .map(e => e[0] + ": " + e[1].toLocaleString() + "<br />");
    //         totalSentKRW = api
    //             .column( 4 )
    //             .data()
    //             .reduce( function (a, b) {
    //                 return intVal(a) + intVal(b);
    //             }, 0 );
    //         totalReceivedKRW = api
    //             .column( 5 )
    //             .data()
    //             .reduce( function (a, b) {
    //                 return intVal(a) + intVal(b);
    //             }, 0 );
 
    //         // Update footer
    //         $(api.column(3).footer()).html(totalSentOriginalString);
    //         $( api.column(4).footer() ).html('₩' + totalSentKRW.toLocaleString());        
    //         $( api.column(5).footer() ).html('₩' + totalReceivedKRW.toLocaleString());        
    // });

    $('#transactions tbody').on('click', 'td.details-control', function () {
        var tr = $(this).closest('tr');
        var row = table.row( tr );
 
        if ( row.child.isShown() ) {
            // This row is already open - close it
            row.child.hide();
            tr.removeClass('shown');
        }
        else {
            // First close all open rows
            $('tr.shown').each(function() {
                table.row(this).child.hide();
                $(this).removeClass('shown');
            })
            // Open this row
            row.child( format(row, row.data()) ).show();
            tr.addClass('shown');
            // $('.btn-save').on('click', function() {
            //     var transaction_node = $(this).closest('.transaction-details');
            //     var update = {
            //         id: row.data().id,
            //         amount: $('#amount', transaction_node).val(),
            //         evidence: $('#evidence', transaction_node).val()
            //     };
            //     $('.wait').show();
            //     $.ajax({
            //         url: '/api/v1/admin/transaction/' + update.id,
            //         method: 'post',
            //         dataType: 'json',
            //         contentType: 'application/json',
            //         data: JSON.stringify(update),
            //         complete: function() {
            //             $('.wait').hide();
            //         },
            //         success: function(data) {
            //             row.data(data).draw();
            //         }
            //     })
            // });
        }
    } );
});

/**
 * Draws order product details
 * @param {object} row - row object 
 * @param {object} data - data object for the row
 */
function format ( row, data ) {
    var transaction_details = $('.transaction-details')
        .clone()
        .removeClass('transaction-details-template')
        .show();
    $('#evidence', transaction_details).attr('src', data.evidence_image);
    $('#currency_code', transaction_details).text(data.currency_code);
    $('#amount_original', transaction_details).val(data.amount_original);
    $('#amount_krw', transaction_details).val(data.amount_krw);
    $('#amount_received_krw', transaction_details).val(data.amount_received_krw);

    $('.currency-dropdown', transaction_details).on('hidden.bs.dropdown', function(target) {
        $('#currency_code', transaction_details).text(target.clickEvent.target.innerText);
        update_amount_krw(transaction_details, data);
    });
    $('#amount_original', transaction_details).on('change', function() {
        update_amount_krw(transaction_details, data);
    });
    $('#amount_krw', transaction_details).on('change', function() {
        data.amount_krw = this.value;
        
    });
    $('#amount_received_krw', transaction_details).on('change', function() {
        data.amount_received_krw = this.value;
    });
    $('#evidence_image', transaction_details).on('change', function() {
        if (this.files[0]) {
            this.nextElementSibling.textContent = 'File is specified';
        }
    });

    if (['approved', 'cancelled'].includes(data.status)) {
        $('.btn-save', transaction_details).hide()
    } else {
        $('.btn-save', transaction_details).on('click', function() {
            save_transaction(row);
        })
    }

    for (var currency in currencies) {
        $('.dropdown-menu', transaction_details).append(
            '<a class="dropdown-item" href="#">' + currency + '</a>'
        );
    }
    return transaction_details;
}

function get_currencies() {
    $.ajax({
        url: '/api/v1/currency',
        success: function(data) {
            currencies = data;
        }
    });
}

function save_transaction(row) {
    $('.wait').show();
    $.ajax({
        url: '/api/v1/admin/transaction/' + row.data().id,
        method: 'post',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            amount_original: row.data().amount_original,
            amount_krw: row.data().amount_krw,
            amount_received_krw: row.data().amount_received_krw,
            currency_code: row.data().currency_code
        }),
        complete: function() {
            $('.wait').hide();
        },
        success: function(data) {
            row.data(data).draw();
        }
    });

    var form_data = new FormData();
    form_data.append('file', $('#evidence_image', row.child())[0].files[0]);
    if (form_data) {
        $.ajax({
            url: '/api/v1/transaction/' + row.data().id + '/evidence', 
            method: 'post',
            data: form_data, 
            contentType: false,
            cache: false,
            processData: false
        });
    }
}

/**
 * Sets status of the order
 * @param {*} target - table rows representing orders whose status is to be changed
 * @param {string} status - new status
 */
function setStatus(target, newStatus) {
    if (target.count()) {
        $('.wait').show();
        var remained = 0;
        for (var i = 0; i < target.count(); i++) {
            remained++;
            $.ajax({
                url: '/api/v1/admin/transaction/' + target.data()[i].id,
                method: 'POST',
                dataType: 'json', 
                contentType: 'application/json',
                data: JSON.stringify({
                    'status': newStatus,
                }),
                complete: function() {
                    remained--;
                    if (!remained) {
                        $('.wait').hide();
                    }
                },
                success: function(response, _status, _xhr) {
                    target.cell(
                        (_idx, data, _node) => 
                            data.id === parseInt(response.id), 
                        5).data(response.status).draw();
                }
            });     
        }
    } else {
        alert('Nothing selected');
    }
}

function update_amount_krw(target, target_data) {
    target_data.currency_code = $('#currency_code', target).text();
    target_data.amount_original = $('#amount_original', target).val();
    target_data.amount_krw = parseFloat(target_data.amount_original) / currencies[target_data.currency_code];
    $('#amount_krw', target).val(target_data.amount_krw);
    //target_data.draw();
}