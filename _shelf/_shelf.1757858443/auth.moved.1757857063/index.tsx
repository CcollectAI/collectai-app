import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert } from "react-native";
import supabase from "../../lib/supabaseClient";
import { theme } from "../../src/theme";
import { Link } from "expo-router";

export default function SignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function onSignIn() {
    try {
      if (!supabase) throw new Error("Supabase not configured");
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
    } catch (e:any) {
      Alert.alert("Sign in failed", e.message ?? "Try again");
    }
  }

  return (
    <View style={{ flex:1, backgroundColor: theme.colors.bg, padding: 16, justifyContent:"center" }}>
      <Text style={{ fontSize: 22, fontWeight:"800", marginBottom: 12 }}>Sign In</Text>
      <TextInput placeholder="Email" autoCapitalize="none" value={email} onChangeText={setEmail}
        style={{ backgroundColor:"#fff", borderRadius:14, paddingHorizontal:14, height:46, borderWidth:1, borderColor:theme.colors.border, marginBottom: 10 }} />
      <TextInput placeholder="Password" secureTextEntry value={password} onChangeText={setPassword}
        style={{ backgroundColor:"#fff", borderRadius:14, paddingHorizontal:14, height:46, borderWidth:1, borderColor:theme.colors.border }} />
      <TouchableOpacity onPress={onSignIn} style={{ marginTop: 14, backgroundColor: theme.colors.brand.base, height: 48, borderRadius:14, alignItems:"center", justifyContent:"center" }}>
        <Text style={{ color:"#0F172A", fontWeight:"800" }}>Sign In</Text>
      </TouchableOpacity>
      <Link href="/register" style={{ marginTop: 14, color: theme.colors.muted }}>Create account</Link>
    </View>
  );
}
