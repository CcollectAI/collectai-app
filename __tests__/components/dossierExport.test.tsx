/**
 * DossierReportSection — the export button, RENDERED and PRESSED.
 *
 * The bug it replaces shipped and reached TestFlight: the button handed an
 * authenticated URL to `Linking.openURL`, the system browser had no session,
 * and a paying member landed on `{"detail":"Authentication required"}`. Nothing
 * static caught that, because the code was type-correct.
 *
 * So this presses it and asserts on the CALL: authed fetch, never a browser
 * hand-off, and a failure that reaches the member instead of a silent log.
 */
import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { Alert, Linking } from 'react-native';
import { DossierReportSection } from '@/components/DossierReportSection';
import { ApiError } from '@/api/httpClient';

jest.mock('@/hooks/useAppTheme', () => ({
  useAppTheme: () => ({ colors: { text: '#000', muted: '#888', border: '#ddd', accent: '#40C9C6', card: '#fff' } }),
}));
jest.mock('expo-file-system/legacy', () => ({
  documentDirectory: 'file:///docs/',
  writeAsStringAsync: jest.fn().mockResolvedValue(undefined),
}));
jest.mock('expo-sharing', () => ({
  isAvailableAsync: jest.fn().mockResolvedValue(true),
  shareAsync: jest.fn().mockResolvedValue(undefined),
}));
const mockFetchHtml = jest.fn();
jest.mock('@/api/collectorsApi', () => ({
  collectorsApi: {
    fetchDossierExportHtml: (...a: unknown[]) => mockFetchHtml(...a),
    getDossierExportUrl: () => 'https://api.example.com/dossier/x/export',
  },
}));

const theme = { text: '#000', muted: '#888', border: '#ddd', accent: '#40C9C6', card: '#fff', background: '#fff', success: '#059669' } as never;
const dossierData = { market_comps: [{}], authenticity_signals: [], identity: {}, valuation: {}, completeness_score: 1 } as never;

const props = {
  theme, dossierData, dossierLoading: false, dossierExpanded: true, dossierError: false,
  onToggleExpanded: jest.fn(), onRetry: jest.fn(), itemId: 'abc12345-0000-0000-0000-000000000000',
  formatPrice: (v: number) => `EUR ${v}`, toNum: (v: unknown) => Number(v),
} as never;

describe('dossier export', () => {
  beforeEach(() => { jest.clearAllMocks(); mockFetchHtml.mockResolvedValue('<html>report</html>'); });

  it('fetches WITH auth and never hands the URL to the browser', async () => {
    const openURL = jest.spyOn(Linking, 'openURL').mockResolvedValue(true);
    const { getByLabelText } = render(<DossierReportSection {...props} />);
    fireEvent.press(getByLabelText(/export/i));
    await waitFor(() => expect(mockFetchHtml).toHaveBeenCalledTimes(1));
    // The whole point: the browser must never see this URL again.
    expect(openURL).not.toHaveBeenCalled();
  });

  it('tells the member WHY the export failed, rather than logging silently', async () => {
    // 2026-09-14: this used to assert the member saw "403". A status code is not
    // a reason — the plan gate writes one, and that sentence is what reaches them.
    mockFetchHtml.mockRejectedValue(
      new ApiError('GET', '/dossier/x/export', 403, 'This feature requires pro plan or higher. Your current plan: free.'),
    );
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    const { getByLabelText } = render(<DossierReportSection {...props} />);
    fireEvent.press(getByLabelText(/export/i));
    await waitFor(() => expect(alert).toHaveBeenCalled());
    const body = String(alert.mock.calls[0][1]);
    expect(body).toMatch(/requires pro plan/);
    expect(body).not.toMatch(/403|GET|\/dossier/);
  });

  it('says a plain sentence on a server failure, never the status line', async () => {
    mockFetchHtml.mockRejectedValue(new ApiError('GET', '/dossier/x/export', 500, 'GET /dossier/x/export failed'));
    const alert = jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    const { getByLabelText } = render(<DossierReportSection {...props} />);
    fireEvent.press(getByLabelText(/export/i));
    await waitFor(() => expect(alert).toHaveBeenCalled());
    expect(String(alert.mock.calls[0][1])).toBe('Could not build the report. Please try again.');
  });
});
