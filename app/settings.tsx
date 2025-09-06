import React, { useEffect, useState } from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import supabase from "../lib/supabaseClient";
import { theme } from "../src/theme";

export default function Settings() {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      if (!supabase) return;
      const { data } = await supabase.auth.getUser();
      setEmail(data.user?.email ?? null);
    })();
  }, []);

  async function onSignOut() {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    } catch (e: any) {
      Alert.alert("Error", e.message ?? "Could not sign out");
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.bg, padding: 16 }}>
      <Text style={{ fontSize: 22, fontWeight: "800", marginBottom: 16 }}>Settings</Text>

      <View style={{ backgroundColor: "#fff", borderRadius: 16, padding: 16, borderWidth: 1, borderColor: theme.colors.border }}>
        <Text style={{ color: theme.colors.muted, marginBottom: 6 }}>Signed in as</Text>
        <Text style={{ fontWeight: "800", color: theme.colors.text }}>{email ?? "—"}</Text>
      </View>

      <TouchableOpacity onPress={onSignOut} style={{ marginTop: 16, backgroundColor: "#fff", borderRadius: 16, borderWidth: 1, borderColor: theme.colors.border, padding: 14, alignItems: "center" }}>
        <Text style={{ color: theme.colors.danger, fontWeight: "800" }}>Sign out</Text>
      </TouchableOpacity>
    </View>
  );
}

