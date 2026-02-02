import React from "react";
import { View } from "react-native";
import { Stack } from "expo-router";
import { SettingsProvider } from "@/lib/settings";
import { InboxHeaderButton } from "@/components/InboxHeaderButton";
import { ThemeToggleButton } from "@/components/ThemeToggleButton";
import { useAppTheme } from "@/hooks/useAppTheme";
import { ErrorBoundary } from "@/components/ErrorBoundary";

function HeaderRight() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }}>
      <InboxHeaderButton />
      <ThemeToggleButton />
    </View>
  );
}

function RootStack() {
  const { colors } = useAppTheme();

  return (
    <Stack
      screenOptions={{
        headerShown: true,
        headerRight: () => <HeaderRight />,
        headerStyle: { backgroundColor: colors.card },
        headerTintColor: colors.text,
        headerTitleStyle: { fontWeight: '600' },
      }}
    >
      {/* Tabs group hides Stack header - tabs have their own header */}
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      {/* Named screens with proper titles */}
      <Stack.Screen name="inbox" options={{ headerShown: false }} />
      <Stack.Screen name="chat/[threadId]" options={{ headerShown: false }} />
      <Stack.Screen name="chat/new" options={{ headerShown: false }} />
      <Stack.Screen name="analytics" options={{ title: 'Analytics' }} />
      <Stack.Screen name="twitch" options={{ title: 'Twitch' }} />
      <Stack.Screen name="build-paint-projects" options={{ title: 'Build & Paint' }} />
      <Stack.Screen name="categories/index" options={{ title: 'Categories' }} />
      <Stack.Screen name="categories/[categoryId]" options={{ title: 'Category' }} />
      <Stack.Screen name="projects/[id]" options={{ title: 'Project' }} />
      <Stack.Screen name="users/[id]" options={{ headerShown: false }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <ErrorBoundary>
      <SettingsProvider>
        <RootStack />
      </SettingsProvider>
    </ErrorBoundary>
  );
}
