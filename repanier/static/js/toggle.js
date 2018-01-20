function toggle_display(checked, elementId) {
    for (i = 0; i < elementId.length; i++) {
        if (checked) {
            document.getElementById(elementId[i]).style.display = 'block'
        } else {
            document.getElementById(elementId[i]).style.display = 'none'
        }
    }
}

function toggle_all(parentId, childrenName) {
    parent = document.getElementById(parentId);
    children = document.getElementsByName(childrenName);
    for (var i = 0, n = children.length; i < n; i++) {
        children[i].checked = parent.checked;
    }
    return parent.checked
}

function toggle(parentId, childId, childrenName) {
    all_checked = true;
    none_checked = true;
    child = document.getElementById(childId);
    children = document.getElementsByName(childrenName);
    for (var i = 0, n = children.length; i < n; i++) {
        all_checked &= children[i].checked;
        none_checked &= !children[i].checked
    }
    parent = document.getElementById(parentId);
    parent.checked = all_checked;
    return all_checked
}
