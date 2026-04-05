export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('palm4u_token');
}

export function setToken(token: string): void {
  localStorage.setItem('palm4u_token', token);
}

export function clearToken(): void {
  localStorage.removeItem('palm4u_token');
}

export function isAuthenticated(): boolean {
  return !!getToken();
}
