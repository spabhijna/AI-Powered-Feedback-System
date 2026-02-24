// Dynamic configuration for different deployment environments
// This allows the frontend to work on any domain without rebuilding
window.CONFIG = {
    // Use the current origin (protocol + domain + port) for API requests
    // This automatically adapts to localhost, production domains, or any deployment
    API_BASE: window.location.origin
};
