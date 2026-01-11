import React from "react";
import { Redirect, useLocalSearchParams } from "expo-router";

export default function UserRedirect() {
  const { userId } = useLocalSearchParams<{ userId?: string | string[] }>();
  const raw = Array.isArray(userId) ? userId[0] : userId;
  const id = raw ? decodeURIComponent(String(raw)) : "";
  return <Redirect href={{ pathname: "/users-card/[userId]" as any, params: { userId: id } }} />;
}
