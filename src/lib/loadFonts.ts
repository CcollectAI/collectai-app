import * as Font from 'expo-font';

// Load the local Ionicons.ttf we just copied into assets/fonts.
// Using a local require() guarantees Metro includes it in the bundle.
export async function loadVectorFonts() {
  try {
    await Font.loadAsync({
      Ionicons: require('../../assets/fonts/Ionicons.ttf'),
    });
    console.log('[fonts] Ionicons (local) loaded');
  } catch (e) {
    console.warn('[fonts] Ionicons failed to load', e);
  }
}
