document.addEventListener("DOMContentLoaded", function() {
    // Écoute les clics sur tous les liens contenant open-order ou close-order
    document.querySelectorAll('a[href*="open-order"], a[href*="close-order"]').forEach(link => {
        link.addEventListener('click', function(e) {
            // Extrait l'ID de la permanence depuis l'attribut href (ex: /.../123/open-order/)
            const href = this.getAttribute('href');
            const match = href.match(/\/(\d+)\/(open-order|close-order)/);

            if (match && match[1]) {
                const permanenceId = match[1];
                // Active le marqueur unique de rechargement pour cette permanence précise
                sessionStorage.setItem('repanier_trigger_reload_' + permanenceId, 'true');
            }
        });
    });
});