import React from "react";
import { Redirect, useLocalSearchParams } from "expo-router";

export default function UserIdAliasRedirect() {
  const { id } = useLocalSearchParams<{ id?: string | string[] }>();
  const raw = Array.isArray(id) ? id[0] : id;
  const userId = raw ? decodeURIComponent(String(raw)) : "";
  return <Redirect href={{ pathname: "/users-card/[userId]" as any, params: { userId } }} />;
}
