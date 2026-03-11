import { Redirect } from 'expo-router';
import { ScreenErrorBoundary } from '@/components/ScreenErrorBoundary';

function SearchRedirect() {
  return <Redirect href="/(tabs)/marketplace" />;
}

export default function SearchRedirectWithBoundary() {
  return (
    <ScreenErrorBoundary screenName="Search">
      <SearchRedirect />
    </ScreenErrorBoundary>
  );
}
