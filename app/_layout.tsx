import { useSession } from "../src/auth/useSession";
import { ActivityIndicator, View } from "react-native";
// ...

export default function RootLayout() {
  const { ready, signedIn } = useSession();

  if (!ready) {
    return (
      <View style={{ flex:1, alignItems:"center", justifyContent:"center" }}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <Stack
      // (keep your existing screenOptions + headerRight gear)
    >
      {signedIn ? (
        <>
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen name="settings" options={{ title: "Settings" }} />
        </>
      ) : (
        <>
          <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        </>
      )}
    </Stack>
  );
}
