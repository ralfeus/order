var NO_SHIPPING_ID = 4;

function round_up(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}

function modal(title, text, type='info') {
    var promise = $.Deferred();
    $('.modal-title').text(title);
    $('.modal-body').html(text);
    if (type == 'confirmation') {
        $('.modal-footer').html(
            '<button type="button" id="btn-yes" class="btn btn-danger"  data-dismiss="modal">Yes</button>' +
            '<button type="button" class="btn btn-secondary" data-dismiss="modal">No</button>'
        );
        $('#btn-yes').on('click', () => {promise.resolve('yes')});
    } else {
        $('.modal-footer').html(
            '<button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>'
        );
    }
    $('.modal').modal();
    return promise;
}

function format_date(date) {
    if (date.valueOf()) {
        d = [ date.getFullYear() ].concat([
            '0' + (date.getMonth() + 1),
            '0' + date.getDate(),
            '0' + date.getHours(),
            '0' + date.getMinutes()
        ].map(component => component.slice(-2))); // take last 2 digits of every component

        // join the components into date
        return d.slice(0, 3).join('-') + ' ' + d.slice(3).join(':');
    } else {
        return '';
    }
}

async function get_currencies() {
    return await get_list('/api/v1/currency');
}

async function get_list(url) {
    return (await fetch(url)).json();
}

async function get_payment_methods() {
    return await get_list('/api/v1/payment/method');
}

async function get_users() {
    return await get_list('/api/v1/admin/user');
}

function init_search(table, filter_sources) {
    var promise = $.Deferred();
    var columns_left = table.api().columns().count();
    table.api().columns().every(function() { 
        column = this;
        $('td:nth-child(' + (this.index() + 1) + ') input', 
            $(this.header()).closest('thead'))
            .each((_idx, item) => init_search_input(item, column))
            .val('');
        $('td:nth-child(' + (this.index() + 1) + ') select', 
            $(this.header()).closest('thead'))
            .each((_idx, item) => init_search_select(
                item, column, filter_sources[column.dataSrc()]))
            .val('');
        columns_left--;
        if (!columns_left) {
            promise.resolve();
        }
    });
    return promise;
}

function init_search_input(target, column) {
    $(target).on('keyup change clear', function () {
        if ( column.search() !== this.value ) {
            column
                .search( this.value )
                .draw();
            // console.log(column.dataSrc(), this.value);
        }
    });
}

function init_search_select(target, column, list) {
    $(target).select2({
        data: list,
        multiple: true
    })
    .on('change', function() {
        var selected_items = $(target).select2('data').map(e => e.id);
        var search_term = column.table().settings()[0].oInit.serverSide
            ? selected_items.join(',')
            : selected_items.join('|');
        if (column.search() !== search_term) {
            if (column.table().settings()[0].oInit.serverSide) {
                column
                    .search(selected_items)
                    .draw();
            } else {
                column
                    .search(search_term, true, false)
                    .draw();
            }
        }
    });    
}

function init_table_filter(table) {
    var params = new URLSearchParams(window.location.search);
    params.forEach((value, key) => {
        var column = table.api().column(key + ':name');
        $('td:nth-child(' + (column.index() + 1) + ') input', 
            $(column.header()).closest('thead'))
            .val(value).trigger('change');
        $('td:nth-child(' + (column.index() + 1) + ') select', 
            $(column.header()).closest('thead'))
            .val(value).trigger('change');
    });
}

$(document).ready(function(){
    $('.dropdown-submenu>a').on("click", function(e){
      $(this).next('ul').toggle();
      e.stopPropagation();
      e.preventDefault();
    });
  });
