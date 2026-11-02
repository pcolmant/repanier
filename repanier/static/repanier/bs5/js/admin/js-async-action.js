document.addEventListener("DOMContentLoaded", function() {
    document.querySelectorAll('.js-async-action').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const url = this.dataset.url;
            if (!url) return;

            // 1. Sauvegarder l'icône originale et afficher le spinner de chargement
            const originalHTML = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin" style="color: #32CD32;"></i>';

            // 2. Appel asynchrone (Fetch) vers la vue Django
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Content-Type': 'application/json'
                }
            })
            .then(response => {
                if (response.ok) {
                    return response.json().catch(() => ({ success: true }));
                }
                throw new Error('Erreur serveur');
            })
            .then(data => {
                // 3. Succès : l'icône devient une coche verte
                this.innerHTML = '<i class="fas fa-check" style="color: #32CD32;"></i>';
                setTimeout(() => {
                    this.innerHTML = originalHTML; // Restauration après 2 secondes
                    this.disabled = false;
                }, 2000);
            })
            .catch(error => {
                // 4. Erreur : l'icône devient une croix rouge
                this.innerHTML = '<i class="fas fa-exclamation-triangle" style="color: Tomato;"></i>';
                this.disabled = false;
                setTimeout(() => {
                    this.innerHTML = originalHTML;
                }, 3000);
            });
        });
    });
});