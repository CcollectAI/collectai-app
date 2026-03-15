/**
 * Error Boundary Component
 *
 * Catches JavaScript errors in child component tree and displays fallback UI.
 * Prevents entire app from crashing due to unhandled errors.
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { View, Text, StyleSheet, Pressable, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useAppTheme } from '@/hooks/useAppTheme';
import { BRAND_COLORS } from '@/constants/colors';
import logger from '@/utils/logger';

/* ---------- Sentry (guarded so builds work before `npm i`) ---------- */
import type { SentryModule } from '@/../types/api';
let Sentry: SentryModule | null = null;
try {
  Sentry = require('@sentry/react-native');
} catch (_) {
  // @sentry/react-native not installed – skip silently
}

/** Functional fallback UI that respects dark mode */
function ErrorFallback({
  error,
  errorInfo,
  onRetry,
}: {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  onRetry: () => void;
}) {
  const { colors } = useAppTheme();
  return (
    <View style={[styles.container, { backgroundColor: colors.background }]}>
      <View style={styles.content}>
        <View style={[styles.iconContainer, { backgroundColor: colors.dangerBg }]}>
          <Ionicons name="warning-outline" size={48} color={colors.danger} />
        </View>
        <Text style={[styles.title, { color: colors.text }]}>Something went wrong</Text>
        <Text style={[styles.subtitle, { color: colors.muted }]}>
          We encountered an unexpected error. Please try again.
        </Text>

        {__DEV__ && error && (
          <ScrollView style={[styles.errorDetails, { backgroundColor: colors.dangerBg }]}>
            <Text style={[styles.errorTitle, { color: colors.danger }]}>Error Details (Dev Only):</Text>
            <Text style={[styles.errorMessage, { color: colors.danger }]}>
              {error.toString()}
            </Text>
            {errorInfo && (
              <Text style={[styles.errorStack, { color: colors.danger }]}>
                {errorInfo.componentStack}
              </Text>
            )}
          </ScrollView>
        )}

        <Pressable style={[styles.retryButton, { backgroundColor: colors.accent }]} onPress={onRetry} accessibilityRole="button" accessibilityLabel="Try again">
          <Ionicons name="refresh-outline" size={20} color={colors.accentText} />
          <Text style={[styles.retryButtonText, { color: colors.accentText }]}>Try Again</Text>
        </Pressable>
      </View>
    </View>
  );
}

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });

    // Report to Sentry if available
    if (Sentry?.captureException) {
      Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
    }

    // Call optional error handler (e.g., for logging to Sentry)
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log error
    if (__DEV__) {
      logger.error('ErrorBoundary caught an error:', error);
      logger.error('Component stack:', errorInfo.componentStack);
    }
  }

  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI (functional component for theme hook access)
      return (
        <ErrorFallback
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          onRetry={this.handleRetry}
        />
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  content: {
    alignItems: 'center',
    maxWidth: 400,
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    // backgroundColor set inline via colors.dangerBg
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  errorDetails: {
    maxHeight: 200,
    width: '100%',
    // backgroundColor set inline via colors.dangerBg
    borderRadius: 8,
    padding: 12,
    marginBottom: 24,
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: '600',
    // color set inline via colors.danger
    marginBottom: 8,
  },
  errorMessage: {
    fontSize: 11,
    // color set inline via colors.danger
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  errorStack: {
    fontSize: 10,
    // color set inline via colors.danger
    fontFamily: 'monospace',
  },
  retryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    // backgroundColor set inline via colors.accent
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    gap: 8,
  },
  retryButtonText: {
    // color set inline via colors.accentText
    fontSize: 16,
    fontWeight: '600',
  },
});

export default ErrorBoundary;
