export type PortfolioPoint = { t: number; v: number };

type PortfolioAnalyticsState = {
  points: PortfolioPoint[];
  setPoints: (pts: PortfolioPoint[]) => void;
};

const _state: PortfolioAnalyticsState = {
  points: [],
  setPoints: (pts) => {
    _state.points = Array.isArray(pts) ? pts : [];
  },
};

export function getPortfolioAnalyticsStore(): PortfolioAnalyticsState {
  return _state;
}
