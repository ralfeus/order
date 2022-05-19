var g_rates_table;

$(document).ready(() => {
    $.ajax({
        url: `/api/v1/admin/shipping/dhl/rate`,
        success: data => {         
            var columns = [{data: 'weight', title: 'weight'}];
            var column_names = Object.keys(data.data[0]);
            for (var column of column_names) {
                if (column == 'weight') {
                    continue;
                }
                columns.push({
                    data: column,
                    title: column
                });
            }
            $('#rates').DataTable({
                lengthChange: false,
                buttons: [
                    { text: "Import Excel", action: import_excel },
                    'pageLength'
                ],
                data: data.data,
                rowId: 'weight',
                columns: columns,
                initComplete: function() { 
                    var table = this;
                    this.api().buttons().container().appendTo( '#rates_wrapper .col-sm-12:eq(0)' ); 
                }        
            });
        }
    });
});

function import_excel() {

}