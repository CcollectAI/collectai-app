/**
 * Auth route group layout — headerless stack for login/register/onboarding.
 */
import { Stack } from 'expo-router';

export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
