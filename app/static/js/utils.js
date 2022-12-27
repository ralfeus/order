var NO_SHIPPING_ID = 4;
const fmtKRW = new Intl.NumberFormat('KR-kr', {style: 'currency', currency: 'KRW'});

function round_up(number, signs) {
    return Math.ceil(number * Math.pow(10, signs)) / Math.pow(10, signs);
}

var is_modals_on = true;
function modals_off() {
    is_modals_on = false;
}

function modals_on() {
    is_modals_on = true;
}

function modal(title, text, type='info', params=[]) {
    var promise = $.Deferred();
    if (!is_modals_on) {
        return promise.resolve(false);
    }
    $('.modal-title').text(title);
    $('.modal-body').html(text);
    if (type == 'confirmation') {
        $('.modal-footer').html(
            '<button type="button" id="btn-yes" class="btn btn-danger"  data-dismiss="modal">Yes</button>' +
            '<button type="button" class="btn btn-secondary" data-dismiss="modal">No</button>'
        );
        $('#btn-yes').on('click', () => {promise.resolve('yes')});
    } else if (type == 'form') {
        $('.modal-body').html(params.reduce(
            (html, input) => html + 
                '<div class="form-group">' +
                    "<label>" + input.label + '</label>' +
                    '<input class="form-control"' +
                        'name="' + input.name + '" ' +
                        'value="' + (input.value ? input.value : "") + '"/>' +
                '</div>',
                ''));
        $('.modal-body input').on('keypress', e => {
            if (e.originalEvent.key == 'Enter') {
                $('.modal-footer #btn-ok').trigger('click')
            }
        });
        $('.modal-footer').html(
            '<button type="button" id="btn-ok" class="btn btn-success" data-dismiss="modal">Ok</button>' +
            '<button type="button" class="btn btn-cancel" data-dismiss="modal">Cancel</button>'
        );
        $('.modal-footer #btn-ok').on('click', () => {
            var result = $('.modal-body input').toArray().reduce((acc, input) => 
                ({[input.name]: input.value, ...acc}), {});
            promise.resolve(result);
        })
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
    return (await get_list('/api/v1/currency')).data;
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
            .each((_idx, item) => {
                var column_name = column.settings()[0].aoColumns[column.index()].name;
                init_search_select(
                    item, column, filter_sources[column_name ? column_name : column.dataSrc()])
            })
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
                .search(this.value, false)
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
                    .search(search_term
                        .replace('(', '\\(').replace(')', '\\)'), true, false)
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

function relativize_time(time) {
    const units = {
        year: 31536000000,
        month: 2592000000,
        week: 604800000,
        day: 86400000,
        hour: 3600000,
        minute: 60000,
        second: 1000
    };
    const time_delta = new Date(time) - new Date();
    const language = navigator.language.slice(0, 2);
    const rtf = new Intl.RelativeTimeFormat(language, { numeric: 'auto' });
    for (const unit in units) {
        const units_ago = Math.round(time_delta / units[unit]);
        if (Math.abs(units_ago) > 1) {
            return rtf.format(units_ago, unit);
        }
    }
    return 'now';
}

$(document).ready(function(){
    $('.dropdown-submenu>a').on("click", function(e){
      $(this).next('ul').toggle();
      e.stopPropagation();
      e.preventDefault();
    });
  });

var dt_render_local_time = function(data, type, _row) {
    if (data === null) {
        return null;
    }
    if (type == 'display') {
        var time = new Date(data);
        return new Date(time + ' GMT+2')
            .toLocaleString(navigator.language, {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour12: false,
                hour: '2-digit',
                minute: '2-digit'
            });
    } else {
        return data;
    }
}