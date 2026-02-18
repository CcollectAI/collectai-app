import React, { ReactNode } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface Props {
  children: ReactNode;
  screenName?: string;
}

function ScreenFallback({ screenName, onRetry }: { screenName?: string; onRetry: () => void }) {
  return (
    <View style={styles.container}>
      <View style={styles.iconWrap}>
        <Ionicons name="alert-circle-outline" size={40} color="#EF4444" />
      </View>
      <Text style={styles.title}>
        {screenName ? `${screenName} failed to load` : 'Screen failed to load'}
      </Text>
      <Text style={styles.subtitle}>
        An error occurred. Please try again.
      </Text>
      <Pressable style={styles.retry} onPress={onRetry} accessibilityRole="button">
        <Ionicons name="refresh-outline" size={18} color="#fff" />
        <Text style={styles.retryText}>Retry</Text>
      </Pressable>
    </View>
  );
}

export class ScreenErrorBoundary extends React.Component<Props, { hasError: boolean }> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  handleRetry = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <ScreenFallback
          screenName={this.props.screenName}
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
    padding: 32,
    backgroundColor: '#F7FAF9',
  },
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#FEE2E2',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    color: '#0F172A',
    textAlign: 'center',
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 13,
    color: '#64748B',
    textAlign: 'center',
    marginBottom: 20,
  },
  retry: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#81D8D0',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
    gap: 6,
  },
  retryText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
  },
});

export default ScreenErrorBoundary;
