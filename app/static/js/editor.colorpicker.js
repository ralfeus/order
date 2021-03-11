//plugin
// colorpicker field type plug-in code
(function ($, DataTable) {
 
    if ( ! DataTable.ext.editorFields ) {
        DataTable.ext.editorFields = {};
    }
     
    var Editor = DataTable.Editor;
    var _fieldTypes = DataTable.ext.editorFields;
     
    _fieldTypes.colorpicker = {
        create: function ( conf ) {
            var that = this;
     
            conf._enabled = true;
     
            // Create the elements to use for the input
            conf._input = $(
                '<div id="' + Editor.safeId(conf.id) + '">' +
                    '<input type="text" class="basic" id="spectrum"/>' +
                    '<em id="basic-log"></em>' +
                    '</div>');
     
            // Use the fact that we are called in the Editor instance's scope to call
            // input.ClassName
            $("input.basic", conf._input).spectrum({
                //color: "#f00",
                change: function (color) {
                    $("#basic-log").text(color.toHexString());
                }
            });
            return conf._input;
        },
     
        get: function (conf) {
            var val = $("input.basic", conf._input).spectrum("get").toHexString();
            return val;
        },
     
        set: function (conf, val) {
            $("input.basic", conf._input).spectrum({
                color: val,
                change: function (color) {
                    $("#basic-log").text("change called: " + color.toHexString());
                }
            });          
        },
     
        enable: function ( conf ) {
            conf._enabled = true;
            $(conf._input).removeClass( 'disabled' );
        },
     
        disable: function ( conf ) {
            conf._enabled = false;
            $(conf._input).addClass( 'disabled' );
        }
    };
})(jQuery, jQuery.fn.dataTable);