import React, { useState } from "react";
import { View, Text, Alert, ActivityIndicator } from "react-native";
import { supabase } from "../../lib/supabase";
import { router } from "expo-router";
import Input from '@/components/ui/Input";
import Button from '@/components/ui/Button";

export default function SignUp() {
  const [username, setUsername] = useState("");
  const [email, setEmail]       = useState("");
  const [pass, setPass]         = useState("");
  const [loading, setLoading]   = useState(false);

  async function onSignUp() {
    try {
      setLoading(true);
      if (!username || !email || !pass) {
        Alert.alert("Missing fields", "Please enter username, email and password.");
        return;
      }

      const { data, error } = await supabase.auth.signUp({
        email,
        password: pass,
      });
      if (error) throw error;

      const user = data.user;
      if (!user) {
        Alert.alert("Check your email", "Confirm your address to finish sign up.");
        router.replace("/(auth)");
        return;
      }

      // Insert profile (username must be unique)
      const { error: pErr } = await supabase.from("profiles").insert({
        id: user.id,
        username,
      });
      if (pErr) {
        // If duplicate username, tell them
        if ((pErr as any).code === "23505") {
          Alert.alert("Username taken", "Please choose another username.");
          return;
        }
        throw pErr;
      }

      Alert.alert("Account created", "You can now sign in.");
      router.replace("/(auth)");
    } catch (e: any) {
      Alert.alert("Sign up failed", e?.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 20, gap: 14, justifyContent: "center" }}>
      <Text style={{ fontSize: 24, fontWeight: "800", marginBottom: 4 }}>Create account</Text>

      <Input
        label="Username"
        placeholder="yourname"
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
      />
      <Input
        label="Email"
        placeholder="you@example.com"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <Input
        label="Password"
        placeholder="••••••••"
        secureTextEntry
        value={pass}
        onChangeText={setPass}
      />

      {loading ? (
        <ActivityIndicator />
      ) : (
        <Button title="Create account" onPress={onSignUp} />
      )}

      <View style={{ height: 10 }} />
      <Text
        onPress={() => router.replace("/(auth)")}
        style={{ textAlign: "center", color: "#2563eb", fontWeight: "600" }}
      >
        Already have an account? Sign in
      </Text>
    </View>
  );
}
