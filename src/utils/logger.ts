/**
 * Sparrow logger — re-export of the single implementation in `@/lib/logger`.
 *
 * There used to be TWO logger implementations with DIFFERENT production
 * semantics: this one stripped `warn` behind __DEV__, while `@/lib/logger`
 * always printed it. 102 files import this one and 44 the other, so whether
 * `logger.warn('request failed')` survived into a release build depended
 * entirely on which import a file happened to have — invisible at the call
 * site, and impossible to reason about when reading a screen.
 *
 * That is the duplicate-implementation trap: a fix applied to one copy does
 * nothing for the other, and both typecheck. Collapsed to one implementation so
 * there is a single answer to "is this visible in production?".
 *
 * Behaviour now, for every caller:
 *   debug/info   console output only in __DEV__
 *   warn/error   always printed
 *   ALL levels   retained in a bounded ring buffer, readable via getRecentLogs()
 *
 * The default export is preserved, so existing
 * `import logger from '@/utils/logger'` call sites keep working unchanged.
 */
import { createLogger } from '@/lib/logger';

export { getRecentLogs, clearRecentLogs, createLogger } from '@/lib/logger';
export type { RetainedLog } from '@/lib/logger';

const logger = createLogger({ prefix: 'Sparrow' });

export { logger };
export default logger;
