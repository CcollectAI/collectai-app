import React from "react";
import { Redirect } from "expo-router";

/**
 * Root entry point.
 *
 * Always go straight into the (tabs) group, where the bottom nav
 * (Portfolio / Items / Add / Search) lives.
 */
export default function RootIndex() {
  return <Redirect href="/(tabs)" />;
}
