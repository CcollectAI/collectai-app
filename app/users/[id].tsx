import React from "react";
import { Redirect, useLocalSearchParams } from "expo-router";

/**
 * Compatibility wrapper:
 * Some older links may go to /users/[id].
 * We redirect to /users/[userId] so you only maintain one real screen.
 */
export default function UserIdCompatRoute() {
  const params = useLocalSearchParams();
  const id = String((params as any)?.id ?? "");
  if (!id) return <Redirect href="/users/me" />;
  return <Redirect href={{ pathname: "/users/[userId]", params: { userId: id } }} />;
}
