/**
 * CSRF Protection for AJAX Requests
 * Automatically adds CSRF tokens to all fetch requests
 */

// Get CSRF token from meta tag
function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// Store original fetch
const originalFetch = window.fetch;

// Override fetch to automatically include CSRF token
window.fetch = function(url, options = {}) {
    // Only add CSRF for same-origin requests
    const isSameOrigin = typeof url === 'string' &&
                         (url.startsWith('/') || url.startsWith(window.location.origin));

    if (isSameOrigin) {
        options.headers = options.headers || {};

        // Convert Headers object to plain object if needed
        if (options.headers instanceof Headers) {
            const headersObj = {};
            options.headers.forEach((value, key) => {
                headersObj[key] = value;
            });
            options.headers = headersObj;
        }

        // Add CSRF token for state-changing methods
        const method = (options.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
            options.headers['X-CSRFToken'] = getCSRFToken();
        }
    }

    return originalFetch(url, options);
};

// Also handle XMLHttpRequest for older code
const originalOpen = XMLHttpRequest.prototype.open;
const originalSend = XMLHttpRequest.prototype.send;

XMLHttpRequest.prototype.open = function(method, url, ...args) {
    this._method = method;
    this._url = url;
    return originalOpen.apply(this, [method, url, ...args]);
};

XMLHttpRequest.prototype.send = function(...args) {
    const isSameOrigin = typeof this._url === 'string' &&
                         (this._url.startsWith('/') || this._url.startsWith(window.location.origin));

    if (isSameOrigin && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(this._method.toUpperCase())) {
        this.setRequestHeader('X-CSRFToken', getCSRFToken());
    }

    return originalSend.apply(this, args);
};

console.log('CSRF protection initialized');
