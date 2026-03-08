import React from "react";
import { Redirect, type Href } from "expo-router";

export default function Index() {
  return <Redirect href={"/portfolio" as Href} />;
}
