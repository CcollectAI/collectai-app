import * as Font from 'expo-font';
import { logger } from '@/lib/logger';

// Load the local Ionicons.ttf we just copied into assets/fonts.
// Using a local require() guarantees Metro includes it in the bundle.
export async function loadVectorFonts() {
  try {
    await Font.loadAsync({
      Ionicons: require('../../assets/fonts/Ionicons.ttf'),
    });
    logger.info('[fonts] Ionicons (local) loaded');
  } catch (e) {
    logger.warn('[fonts] Ionicons failed to load', e);
  }
}
