export const environment = {
  production: false,
  apiBaseUrl: "http://localhost:5001/api",
  apiFallbackBaseUrl: "http://localhost:500/api",
  cookieOnlyAuth: false,
  inactivity: {
    enabled: false,
    timeoutSeconds: 900,
    warningSeconds: 60,
  },
};
