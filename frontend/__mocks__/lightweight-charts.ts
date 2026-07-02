export const createChart = jest.fn(() => ({
  addLineSeries: jest.fn(() => ({
    setData: jest.fn(),
    update: jest.fn(),
  })),
  addAreaSeries: jest.fn(() => ({
    setData: jest.fn(),
    update: jest.fn(),
  })),
  applyOptions: jest.fn(),
  remove: jest.fn(),
  timeScale: jest.fn(() => ({ fitContent: jest.fn() })),
}));
