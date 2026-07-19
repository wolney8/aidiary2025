export const environment = {
  production: true,
  apiBaseUrl: "http://localhost:5001/api",
  apiFallbackBaseUrl: "http://localhost:500/api",
  inactivity: {
    enabled: true,
    timeoutSeconds: 900,
    warningSeconds: 60,
  },
};
