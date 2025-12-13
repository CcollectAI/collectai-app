import React from "react";
import { View } from "react-native";

/**
 * ItemsOverviewBanner
 *
 * Now behaves as a subtle divider under the Items header / portfolio value.
 * No text, just a Tiffany-style line to visually separate header from the list.
 */
export default function ItemsOverviewBanner() {
  return (
    <View
      style={{
        marginTop: 4,
        marginBottom: 8,
        height: 1,
        backgroundColor: "#D4E4EC", // soft divider line
      }}
    />
  );
}
