import "@testing-library/jest-dom";

// Mock scrollIntoView which jsdom doesn't implement
window.HTMLElement.prototype.scrollIntoView = jest.fn();

// Mock EventSource
class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  readyState = MockEventSource.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  private listeners: Record<string, ((event: Event) => void)[]> = {};

  constructor(public url: string) {}

  addEventListener(type: string, handler: (event: Event) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(handler);
  }

  removeEventListener(type: string, handler: (event: Event) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((h) => h !== handler);
    }
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }

  dispatchEvent(event: Event): boolean {
    const handlers = this.listeners[event.type] ?? [];
    handlers.forEach((h) => h(event));
    return true;
  }
}

(global as unknown as { EventSource: typeof MockEventSource }).EventSource = MockEventSource;
