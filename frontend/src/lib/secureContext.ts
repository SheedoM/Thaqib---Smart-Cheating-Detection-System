export function isLocalDevHost(hostname = window.location.hostname) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
}

export function isInsecureLanContext() {
  return !window.isSecureContext && !isLocalDevHost();
}
