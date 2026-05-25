module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      ['module-resolver', {
        root: ['./'],
        alias: { '@': './src' },
        extensions: ['.tsx', '.ts', '.js', '.jsx', '.json']
      }],
      // Required by react-native-reanimated v4 + react-native-worklets.
      // MUST be the LAST plugin. Without it, worklets don't compile, which
      // breaks reanimated-driven components — including React Navigation v7
      // bottom tabs (uses reanimated internally for tab state transitions).
      // This was the actual root cause of the "tab bar unresponsive" bug
      // that builds #14-23 chased with cosmetic fixes (pointerEvents, splash
      // overlays, GestureHandlerRootView). 2026-05-25.
      'react-native-worklets/plugin',
    ],
  };
};
