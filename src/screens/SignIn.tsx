import React, { useState } from "react";
import { View, Text, Alert, ActivityIndicator } from "react-native";
import { supabase } from "../../lib/supabase";
import { router } from "expo-router";
import Input from '@/components/ui/Input";
import Button from '@/components/ui/Button";

export default function SignIn() {
  const [identifier, setIdentifier] = useState(""); // username or email
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [loading, setLoading] = useState(false);

  async function resolveEmailFromUsername(username: string): Promise<string | null> {
    try {
      const { data, error } = await supabase
        .from("profiles")
        .select("id, username")
        .eq("username", username)
        .limit(1)
        .maybeSingle();
      if (error) throw error;
      // We cannot read email from auth.users client-side.
      // So if user provided email, use it; otherwise return null.
      return email || null;
    } catch {
      return null;
    }
  }

  async function onSignIn() {
    try {
      setLoading(true);
      const looksLikeEmail = identifier.includes("@");
      const finalEmail = looksLikeEmail
        ? identifier.trim()
        : await resolveEmailFromUsername(identifier.trim());

      if (!finalEmail) {
        Alert.alert(
          "Email needed",
          "Enter your email (or use magic link) so we can sign you in."
        );
        return;
      }

      const { error } = await supabase.auth.signInWithPassword({
        email: finalEmail,
        password: pass,
      });
      if (error) throw error;
      router.replace("/(tabs)");
    } catch (e: any) {
      Alert.alert("Sign in failed", e?.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  async function onMagicLink() {
    try {
      setLoading(true);
      const looksLikeEmail = identifier.includes("@");
      const finalEmail = looksLikeEmail ? identifier.trim() : email.trim();
      if (!finalEmail) {
        Alert.alert("Email required", "Provide an email for the magic link.");
        return;
      }
      const { error } = await supabase.auth.signInWithOtp({
        email: finalEmail,
        options: { shouldCreateUser: false },
      });
      if (error) throw error;
      Alert.alert("Check your email", "We sent you a magic sign-in link.");
    } catch (e: any) {
      Alert.alert("Magic link failed", e?.message ?? "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={{ flex: 1, padding: 20, gap: 14, justifyContent: "center" }}>
      <Text style={{ fontSize: 24, fontWeight: "800", marginBottom: 4 }}>Welcome back</Text>
      <Text style={{ color: "#6b7280", marginBottom: 8 }}>
        Sign in with your <Text style={{ fontWeight: "700" }}>username or email</Text>.
      </Text>

      <Input
        label="Username or email"
        placeholder="yourname or you@example.com"
        autoCapitalize="none"
        value={identifier}
        onChangeText={setIdentifier}
      />
      {!identifier.includes("@") ? (
        <Input
          label="Email (needed for magic link / fallback)"
          placeholder="you@example.com"
          autoCapitalize="none"
          value={email}
          onChangeText={setEmail}
        />
      ) : null}
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
        <>
          <Button title="Sign in" onPress={onSignIn} />
          <View style={{ height: 8 }} />
          <Button title="Email me a magic link" onPress={onMagicLink} />
        </>
      )}

      <View style={{ height: 10 }} />
      <Text
        onPress={() => router.push("/(auth)/register")}
        style={{ textAlign: "center", color: "#2563eb", fontWeight: "600" }}
      >
        Need an account? Create one
      </Text>
    </View>
  );
}
