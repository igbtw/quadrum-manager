// Language preference controls.
//
// Authenticated users: radios inside the Preferences dialog POST to
// preferences/language/ and reload the current URL on success (filters,
// sorting and pagination are preserved because the URL is not rebuilt).
// Anonymous users: the auth-page select submits a regular CSRF-protected form
// whose endpoint redirects back to the current route.
(function () {
    'use strict';

    function csrfToken() {
        var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return input ? input.value : '';
    }

    function saveLanguage(url, language) {
        var body = new URLSearchParams();
        body.set('language', language);
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': csrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: body.toString()
        }).then(function (response) {
            if (!response.ok) throw new Error('language request failed');
            return response.json();
        });
    }

    function showLanguageError() {
        var t = (window.quadrum && window.quadrum.t)
            ? window.quadrum.t
            : function (key, fallback) { return fallback; };
        var message = t('language.saveError', 'Could not save the language preference.');
        if (window.quadrum && window.quadrum.showToast) {
            window.quadrum.showToast(t('language.title', 'Language'), message, 'error');
        } else {
            window.alert(message);
        }
    }

    document.addEventListener('change', function (event) {
        var input = event.target.closest('input[data-language-option]');
        if (!input) return;
        var url = input.getAttribute('data-language-url');
        if (!url) return;
        input.disabled = true;
        saveLanguage(url, input.value).then(function () {
            window.location.reload();
        }).catch(function () {
            input.disabled = false;
            showLanguageError();
        });
    });

    document.addEventListener('change', function (event) {
        var select = event.target.closest('select[data-language-select]');
        if (!select) return;
        var form = select.form;
        if (form) form.submit();
    });
})();
