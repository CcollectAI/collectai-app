import React from "react";
import { Redirect } from "expo-router";

/**
 * Legacy route: /home/portfolio
 * Redirects into the Portfolio tab in the main tab layout.
 */
export default function HomePortfolioRedirect() {
  return <Redirect href="/(tabs)" />;
}
