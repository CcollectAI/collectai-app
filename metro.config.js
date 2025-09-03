const { getDefaultConfig } = require('@expo/metro-config');
const config = getDefaultConfig(__dirname);
config.resolver.blockList = [/date-fns\/locale\/(?!en)/];
module.exports = config;
