import { describe, it, expect } from 'vitest';
import { API_BASE, WS_URL, apiUrl } from './api';

describe('api helpers', () => {
  it('uses default local backend URL', () => {
    expect(API_BASE).toBe('http://127.0.0.1:5000');
  });

  it('derives WebSocket URL from API_BASE', () => {
    expect(WS_URL).toBe('ws://127.0.0.1:5000/ws');
  });

  it('builds endpoint URLs with leading slash', () => {
    expect(apiUrl('/trades')).toBe(`${API_BASE}/trades`);
  });

  it('normalizes paths without leading slash', () => {
    expect(apiUrl('metrics')).toBe(`${API_BASE}/metrics`);
  });
});
