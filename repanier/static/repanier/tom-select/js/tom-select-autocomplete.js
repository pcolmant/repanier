var go_from_select = function(opt) {
    if (opt) {
        window.location = window.location.pathname + opt;
    }
};

document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll('.tom-select-autocomplete').forEach((el) => {
        let url = el.dataset.autocompleteUrl;
        if (!url) return;

        let forwardFields = {};
        for (let attr of el.attributes) {
            if (attr.name.startsWith('data-forward-')) {
                let paramName = attr.name.replace('data-forward-', '');
                forwardFields[paramName] = attr.value;
            }
        }

        new TomSelect(el, {
            value_field: 'value',
            label_field: 'text',
            search_field: ['text'],
            load: function(query, callback) {
                let params = new URLSearchParams({ q: query });

                for (let paramName in forwardFields) {
                    let targetId = forwardFields[paramName];
                    let targetEl = document.getElementById(targetId);
                    if (targetEl) {
                        params.append(paramName, targetEl.value);
                    }
                }

                fetch(url + '?' + params.toString())
                    .then(response => response.json())
                    .then(json => callback(json))
                    .catch(() => callback());
            },
            placeholder: "---------",
            allowEmptyOption: true,
            create: false,
            onChange: function(value) {
                if (value) {
                    let permanenceEl = document.getElementById('id_permanence');
                    let permanenceId = permanenceEl ? permanenceEl.value : '';
                    go_from_select('?permanence=' + permanenceId + '&customer=' + value);
                }
            }
        });
    });
});