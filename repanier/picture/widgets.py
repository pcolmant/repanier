# -*- coding: utf-8
from __future__ import unicode_literals

import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.urlresolvers import reverse
from django.forms import widgets
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from repanier.picture.const import SIZE_M
from repanier.const import EMPTY_STRING


class AjaxPictureWidget(widgets.TextInput):
    html = """
    <div id="{element_id}_file_dropbox">
        {input_part}
        <input id="{element_id}" type="hidden" value="{file_path}" name="{name}" />
    </div>
    <script>
        var {element_id}_jQuery;
        if( typeof django === 'undefined'){{
            if( typeof CMS === 'undefined'){{
                {element_id}_jQuery = $
            }} else {{
                {element_id}_jQuery = CMS.$
            }}
        }} else {{
            {element_id}_jQuery = django.jQuery
        }}
        (function($){{
            var {element_id}_file_select = $("#{element_id}_file_select"),
                {element_id}_file_elem = $("#{element_id}_file_elem"),
                {element_id}_file_elem_select = $("#{element_id}_file_elem_select"),
                {element_id}_file_img = $("#{element_id}_file_img"),
                {element_id}_file_dropbox = $("#{element_id}_file_dropbox"),
                {element_id}_file_remove = $("#{element_id}_file_remove"),
                {element_id}_file_path = $("#{element_id}");
            function getCsrftoken() {{
                var cookieValue = null;
                if (document.cookie && document.cookie != '') {{
                    var cookies = document.cookie.split(';');
                    for (var i = 0; i < cookies.length; i++) {{
                        var cookie = $.trim(cookies[i]);
                        // Does this cookie string begin with the name we want?
                        if (cookie.substring(0, 'csrftoken'.length + 1) == ('csrftoken=')) {{
                            csrftoken = decodeURIComponent(cookie.substring('csrftoken'.length + 1));
                            break;
                        }}
                    }}
                }}
                return csrftoken;
            }};
            function addEventHandler(obj, evt, handler) {{
                if(obj.addEventListener) {{
                    // W3C method
                    obj.addEventListener(evt, handler, false);
                }} else if(obj.attachEvent) {{
                    // IE method.
                    obj.attachEvent('on'+evt, handler);
                }} else {{
                    // Old school method.
                    obj['on'+evt] = handler;
                }}
            }};
            function cancel(e) {{
                e.stopPropagation();
                if (e.preventDefault) {{ e.preventDefault(); }}
                return false;
            }};
            function handleFiles(files) {{
                var file = files[0];
                var imageType = /^image\//;
                var file_type = file.type;
                var img = document.createElement("img");
                var reader = new FileReader();
                if (!imageType.test(file_type)) {{
                    alert('{file_is_not_an_image}');
                    return;
                }}
                reader.onloadend  = function() {{
                    var do_not_wait_forever, do_not_do_it_twice, wait_until_img_loaded;
                    img.src = reader.result;
                    function img_loaded() {{
                        var canvas = document.createElement('canvas');
                        var context = canvas.getContext("2d");
                        var MAX_WIDTH = {width};
                        var MAX_HEIGHT = {height};
                        var byteString, mimeString, length, ia, i, file_resized, form_data, csrftoken, width, height;
                        width = img.width;
                        height = img.height;
                        if (width > height) {{
                            if (width > MAX_WIDTH) {{
                                height *= MAX_WIDTH / width;
                                width = MAX_WIDTH;
                            }}
                        }} else {{
                            if (height > MAX_HEIGHT) {{
                                width *= MAX_HEIGHT / height;
                                height = MAX_HEIGHT;
                            }}
                        }}
                        canvas.width = width;
                        canvas.height = height;
                        canvas.style.visibility = "hidden";

                        context.drawImage(img, 0, 0, width, height);
                        if(file_type == 'image/png') {{
                            var dataURL = canvas.toDataURL("image/png");
                        }} else {{
                            var dataURL = canvas.toDataURL("image/jpeg", 0.9);
                        }}
                        if (dataURL.split(',')[0].indexOf('base64') >= 0)
                            byteString = atob(dataURL.split(',')[1]);
                        else
                            byteString = unescape(dataURL.split(',')[1]);
                        mimeString = dataURL.split(',')[0].split(':')[1].split(';')[0];
                        length = byteString.length
                        ia = new Uint8Array(length);
                        for (i = 0; i < length; i++) {{
                            ia[i] = byteString.charCodeAt(i);
                        }}
                        file_resized = new Blob([ia], {{type:mimeString}});
                        form_data = new FormData();
                        form_data.append('file', file_resized, file.name);
                        csrftoken = getCsrftoken();
                        $.ajaxSetup({{
                            beforeSend: function(xhr, settings) {{
                                xhr.setRequestHeader("X-CSRFToken", csrftoken);
                            }}
                        }});
                        $.ajax({{
                            url : "{upload_url}",
                            type : "POST",
                            cache: false,
                            async: true,
                            data: form_data,
                            processData: false,
                            contentType: false,
                            success: function (result) {{
                                var msg = "";
                                $.each(result, function (key, val) {{
                                    if(key == 'url') {{
                                        {element_id}_file_select.attr("href", val);
                                        {element_id}_file_img.attr("src", val);
                                    }} else if(key == 'filename') {{
                                        {element_id}_file_path.val(val);
                                    }} else {{
                                        msg = val;
                                    }}
                                }});
                                {element_id}_file_elem.val("");
                                {element_id}_file_select.css('display', 'inline');
                                {element_id}_file_remove.css('display', 'inline');
                                {element_id}_file_elem.hide();
                                {element_id}_file_elem_select.hide();
                                if(msg != "") {{
                                    alert(msg);
                                    cancel()
                                }}
                            }},
                            error : function(result, errcode, errmsg) {{
                                var obj;
                                if(result.status == 403) {{
                                    obj = JSON.parse(result.responseText);
                                    alert(obj.error)
                                }} else {{
                                    alert(errcode + ": " + errmsg)
                                }}
                            }}
                        }});
                    }}
                    do_not_wait_forever = setTimeout(function(){{
                        clearInterval(wait_until_img_loaded);
                        alert('{stop_waiting}')
                    }},10000);
                    do_not_do_it_twice = 0
                    wait_until_img_loaded = setInterval(function () {{
                        if(img.complete && ++do_not_do_it_twice==1) {{
                            clearTimeout(do_not_wait_forever)
                            clearInterval(wait_until_img_loaded)
                            img_loaded()
                        }}
                    }},100);
                }}
                reader.readAsDataURL(file);
            }}
            function drop(e) {{
                var dt, files;
                cancel(e);
                dt = e.dataTransfer;
                files = dt.files;
                handleFiles(files);
            }}
            {element_id}_file_remove.on('click', function(e){{
                cancel(e);
                {element_id}_file_select.hide();
                {element_id}_file_remove.hide();
                {element_id}_file_elem_select.css('display', 'inline');
                {element_id}_file_path.val("");
            }});
            {element_id}_file_elem.on('change', function(e){{
                cancel(e);
                handleFiles(this.files);
            }});
            {element_id}_file_elem_select.on('click', function(e){{
                {element_id}_file_elem.click();
                cancel(e);
            }});
            addEventHandler({element_id}_file_dropbox, "dragenter", cancel);
            addEventHandler({element_id}_file_dropbox, "dragover", cancel);
            addEventHandler({element_id}_file_dropbox, "drop", drop);
        }}({element_id}_jQuery))
    </script>
    """

    def __init__(self, *args, **kwargs):
        self.upload_to = kwargs.pop('upload_to', 'pictures')
        self.size = kwargs.pop('size', SIZE_M)
        self.bootstrap = kwargs.pop('bootstrap', False)
        super(AjaxPictureWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(attrs)
        element_id = final_attrs.get('id')

        kwargs = {'upload_to': self.upload_to,
                  'size'     : self.size}
        upload_url = reverse('ajax_picture', kwargs=kwargs)

        # NB convert to string and do not rely on value.url
        # value.url fails when rendering form with validation errors because
        # form value is not a FieldFile. Use storage.url and file_path - works
        # with FieldFile instances and string formdata
        if value:
            # Do not replace "if value" with "if value is not None" -> not the same result !
            file_path = str(value)
            display_picture = "inline"
            display_upload = "none"
            file_url = default_storage.url(file_path)
            file_name = os.path.basename(file_url)
        else:
            file_path = EMPTY_STRING
            display_picture = "none"
            display_upload = "inline"
            file_url = EMPTY_STRING
            file_name = EMPTY_STRING

        height = width = self.size

        if self.bootstrap:
            input_part = """
                <a id="{element_id}_file_select" style="display:{display_picture}" target="_blank" href="{file_url}">
                    <img id="{element_id}_file_img" src="{file_url}" class="img-responsive img-thumbnail" style="margin:5px; min-height:32px; min-width:32px; max-height:225px; max-width:225px;">
                </a>
                <p id="{element_id}_file_remove" style="display:{display_picture}"><a id="{element_id}_file_remove" class="btn btn-danger" href="#remove">{remove}</a></p>
                <input id="{element_id}_file_elem" type="file" style="display:none" accept="image/*"/>
                <a href="#" id="{element_id}_file_elem_select" class="btn btn-info" style="display:{display_upload}"><span class="glyphicon glyphicon-camera" aria-hidden="true"></span></a>
            """
        else:
            input_part = """
                <a id="{element_id}_file_select" style="display:{display_picture}" target="_blank" href="{file_url}">
                    <img id="{element_id}_file_img" src="{file_url}" style="min-height:32px; min-width:32px; max-height:225px; max-width:225px;">
                </a>
                <button id="{element_id}_file_remove" style="display:{display_picture}">{remove}&nbsp;<img id="id_picture_clear" src="{static}admin/img/icon_deletelink.gif" alt="{remove}" title="{remove}" height="10" width="10"></button>
                <input id="{element_id}_file_elem" type="file" style="display:none" accept="image/*"/>
                <button id="{element_id}_file_elem_select" style="display:{display_upload}">{select_a_file}</button>
            """

        output_with_input_part = self.html.replace(
            "{input_part}", input_part
        )

        output = output_with_input_part.format(
            upload_url=upload_url,
            file_url=file_url,
            file_name=file_name,
            file_path=file_path,
            element_id=element_id,
            name=name,
            display_picture=display_picture,
            display_upload=display_upload,
            remove="{}".format(_('Remove')),
            file_is_not_an_image="{}".format(_('File is not an image')),
            stop_waiting="{}".format(_('Processing this image take too much time')),
            select_a_file="{}".format(_('Select a picture')),
            width=width,
            height=height,
            static=settings.STATIC_URL
        )

        return mark_safe(output)
