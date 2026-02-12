// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require("expo/metro-config");

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Exclude Python backend files co-located in app/ from Metro bundling
config.resolver.blockList = [
  ...(config.resolver.blockList || []),
  /app\/.*\.py$/,
  /app\/features\/.*/,
  /app\/ml\/.*/,
  /app\/routes\/.*/,
  /app\/routers\/.*/,
  /app\/__init__\.py$/,
  /app\/db\.py$/,
  /app\/auth\.py$/,
  /app\/metrics\.py$/,
  /app\/rate_limit\.py$/,
  /app\/limit_body\.py$/,
  /app\/logging_mw\.py$/,
  /app\/middleware_stack\.py$/,
];

module.exports = config;
