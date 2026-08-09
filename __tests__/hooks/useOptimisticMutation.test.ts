import { renderHook, act, waitFor } from '@testing-library/react-native';
import { useOptimisticMutation } from '../../src/hooks/useOptimisticMutation';

// createLogger is re-exported by src/utils/logger FROM src/lib/logger, so a
// mock omitting it throws "not a function" at IMPORT time — taking the whole
// suite down rather than failing one assertion. Same gap fixed in
// settings.test.tsx today; both had been red for the same reason.
jest.mock('../../src/lib/logger', () => {
  const fns = { warn: jest.fn(), debug: jest.fn(), info: jest.fn(), error: jest.fn() };
  return {
    logger: fns,
    createLogger: () => fns,
    getRecentLogs: () => [],
    clearRecentLogs: jest.fn(),
  };
});

describe('useOptimisticMutation', () => {
  it('calls onOptimisticUpdate synchronously before mutationFn', async () => {
    const order: string[] = [];
    const mutationFn = jest.fn().mockImplementation(async () => {
      order.push('mutation');
      return 'result';
    });
    const onOptimisticUpdate = jest.fn().mockImplementation(() => {
      order.push('optimistic');
    });
    const onRollback = jest.fn();

    const { result } = renderHook(() =>
      useOptimisticMutation({ mutationFn, onOptimisticUpdate, onRollback }),
    );

    await act(async () => {
      await result.current.mutate('args');
    });

    expect(order).toEqual(['optimistic', 'mutation']);
    expect(onOptimisticUpdate).toHaveBeenCalledWith('args');
  });

  it('sets isLoading=true while mutation is in flight', async () => {
    let resolveMutation: (v: string) => void;
    const mutationFn = jest.fn().mockReturnValue(
      new Promise<string>((resolve) => { resolveMutation = resolve; }),
    );

    const { result } = renderHook(() =>
      useOptimisticMutation({
        mutationFn,
        onOptimisticUpdate: jest.fn(),
        onRollback: jest.fn(),
      }),
    );

    act(() => {
      result.current.mutate('test');
    });

    // isLoading should be true while in flight
    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolveMutation!('done');
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('calls onSuccess on successful mutation', async () => {
    const onSuccess = jest.fn();
    const mutationFn = jest.fn().mockResolvedValue('result');

    const { result } = renderHook(() =>
      useOptimisticMutation({
        mutationFn,
        onOptimisticUpdate: jest.fn(),
        onRollback: jest.fn(),
        onSuccess,
      }),
    );

    await act(async () => {
      await result.current.mutate('args');
    });

    expect(onSuccess).toHaveBeenCalledWith('args', 'result');
    expect(result.current.error).toBeNull();
  });

  it('calls onRollback and sets error on mutation failure', async () => {
    const onRollback = jest.fn();
    const err = new Error('API failure');
    const mutationFn = jest.fn().mockRejectedValue(err);

    const { result } = renderHook(() =>
      useOptimisticMutation({
        mutationFn,
        onOptimisticUpdate: jest.fn(),
        onRollback,
      }),
    );

    await act(async () => {
      await result.current.mutate('args');
    });

    expect(onRollback).toHaveBeenCalledWith('args', err);
    expect(result.current.error).toBe(err);
    expect(result.current.isLoading).toBe(false);
  });

  it('clears previous error at start of new mutate call', async () => {
    const mutationFn = jest.fn()
      .mockRejectedValueOnce(new Error('First fail'))
      .mockResolvedValueOnce('ok');

    const { result } = renderHook(() =>
      useOptimisticMutation({
        mutationFn,
        onOptimisticUpdate: jest.fn(),
        onRollback: jest.fn(),
      }),
    );

    // First call fails
    await act(async () => {
      await result.current.mutate('a');
    });
    expect(result.current.error).toBeTruthy();

    // Second call clears error
    await act(async () => {
      await result.current.mutate('b');
    });
    expect(result.current.error).toBeNull();
  });

  it('does not call mutationFn if onOptimisticUpdate throws', async () => {
    const mutationFn = jest.fn().mockResolvedValue('ok');
    const onOptimisticUpdate = jest.fn().mockImplementation(() => {
      throw new Error('Optimistic crash');
    });

    const { result } = renderHook(() =>
      useOptimisticMutation({
        mutationFn,
        onOptimisticUpdate,
        onRollback: jest.fn(),
      }),
    );

    await act(async () => {
      await result.current.mutate('args');
    });

    expect(mutationFn).not.toHaveBeenCalled();
    expect(result.current.error).toBeTruthy();
  });

  it('swallows error if onRollback throws', async () => {
    const mutationFn = jest.fn().mockRejectedValue(new Error('API fail'));
    const onRollback = jest.fn().mockImplementation(() => {
      throw new Error('Rollback crash');
    });

    const { result } = renderHook(() =>
      useOptimisticMutation({
        mutationFn,
        onOptimisticUpdate: jest.fn(),
        onRollback,
      }),
    );

    // Should not throw
    await act(async () => {
      await result.current.mutate('args');
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.isLoading).toBe(false);
  });

  it('returns stable mutate reference across renders', () => {
    const { result, rerender } = renderHook(() =>
      useOptimisticMutation({
        mutationFn: jest.fn().mockResolvedValue('ok'),
        onOptimisticUpdate: jest.fn(),
        onRollback: jest.fn(),
      }),
    );

    const first = result.current.mutate;
    rerender({});
    expect(result.current.mutate).toBe(first);
  });
});
