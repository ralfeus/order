var g_addresses = [];
var g_banks = [
    {value: "03", label: '기업'},
    {value: "07", label: '수협'},
    {value: "31", label: '대구'},
    {value: "06", label: '국민'},
    {value: "11", label: '농협'},
    {value: "81", label: 'KEB하나'},
    {value: "20", label: '우리'},
    {value: "26", label: '신한'},
    {value: "39", label: '경남'},
    {value: "71", label: '우체국'},
    {value: "32", label: '부산'}
]

$(document).ready(() => {
    get_dictionaries()
    .then(init_table);
});

async function get_dictionaries() {
    g_addresses = await get_list('/api/v1/address');
}

function init_table() {
    function advanced_taxation_hide() {
        editor.field('tax_phone').hide();
        editor.field('tax_address.id').hide();
        editor.field('email').hide();
        editor.field('business_type').hide();
        editor.field('business_category').hide();
    }
    
    function advanced_taxation_show() {
        editor.field('tax_phone').show();
        editor.field('tax_address.id').show();
        editor.field('email').show();
        editor.field('business_type').show();
        editor.field('business_category').show();
    }

    function normalize_and_stringify(input) {
        input.default = input.default[0];
        input.enabled = input.enabled[0];
        input.tax_simplified = input.tax_simplified[0];
        return JSON.stringify(input);
    }
        
    var editor = new $.fn.dataTable.Editor({
        ajax: {
            create: {
                url: '/api/v1/admin/purchase/company',
                contentType: 'application/json',
                data: data => normalize_and_stringify(Object.entries(data.data)[0][1])
            },
            edit: {
                url: '/api/v1/admin/purchase/company/_id_',
                contentType: 'application/json',
                data: data => normalize_and_stringify(Object.entries(data.data)[0][1])
            },
            remove: {
                url: '/api/v1/admin/purchase/company/_id_',
                method: 'delete'
            }
        },
        table: '#companies',
        idSrc: 'id',
        fields: [
            { label: 'Name', name: 'name' },
            {label: 'Tax_id', name: 'tax_id'},
            {label: 'Phone', name: 'phone'},
            { 
                label: 'Address',
                name: 'address.id',
                type: 'select2',
                options: g_addresses.map(c => ({
                    value: c.id,
                    label: c.name
                }))                
            },                 
            {
                label: 'Bank', 
                name: 'bank_id',
                type: 'select2',
                options: g_banks
            },
            {label: 'Contact_person', name: 'contact_person'},
            {
                label: 'Default',
                name: 'default',
                type: 'checkbox',
                options: [{label:'', value: true}],
                def: false,
                unselectedValue: false
            },
            {
                label: 'Enabled',
                name: 'enabled',
                type: 'checkbox',
                options: [{label:'', value: true}],
                def: true,
                unselectedValue: false
            },
            {label: 'Taxation type', name: 'tax_type', type: 'title'},
            {
                label: 'Simplified taxation', 
                name: 'tax_simplified', 
                type: 'checkbox', 
                options: [{label:'', value:true}],
                def: true,
                unselectedValue: false
            },
            {label: 'Tax phone', name: 'tax_phone'},
            {
                label: 'Tax address',
                name: 'tax_address.id',
                type: 'select2',
                options: g_addresses.map(c => ({
                    value: c.id,
                    label: c.name
                }))                
            },
            {label: 'E-mail', name: 'email'},
            {label: 'Business type', name: 'business_type'},
            {label: 'Business category', name: 'business_category'}
        ]
    });
    editor.on('open', () => {
        if (editor.field('tax_simplified').val()[0]) {
            advanced_taxation_hide();
        }
    });
    editor.field('tax_simplified').input().on('click', event => {
        if (event.target.checked) {
            advanced_taxation_hide();
        } else {
            advanced_taxation_show();
        }
    });
    $('#companies').DataTable({
        dom: 'Btp',
        ajax: {
            url: '/api/v1/admin/purchase/company',
            dataSrc: ''
        },
        buttons: [
            {extend: 'create', editor: editor, text: 'New'},
            {extend: 'edit', editor: editor, text: 'Edit'},
            {extend: 'remove', editor: editor, text: 'Delete'}
        ],
        columns: [
            {data: 'id'},
            {data: 'name'},
            {data: 'enabled'},
            {data: 'tax_id'},
            {data: 'phone'},
            {data: 'address.name'},
            {data: 'bank_id', render: v => g_banks.filter(e => e.value == v)[0].label},
            {data: 'contact_person'},
            {data: 'tax_simplified'}
        ],
        select: true
    });
}