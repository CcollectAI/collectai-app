import usePortfolio from "./usePortfolio";

export function usePortfolioSeries() {
  const { series, rows, current, delta, deltaPct, loading, error } = usePortfolio();
  return { series, rows, current, delta, deltaPct, loading, error };
}
export default usePortfolioSeries;
