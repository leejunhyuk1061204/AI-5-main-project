const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

config.resolver.extraNodeModules = {
    ...config.resolver.extraNodeModules,
    crypto: require.resolve('expo-crypto'),
    stream: require.resolve('readable-stream'),
    buffer: require.resolve('buffer'),
    events: require.resolve('events'),
    url: require.resolve('url'),
    http: require.resolve('stream-http'),
    https: require.resolve('https-browserify'),
    zlib: require.resolve('browserify-zlib'),
    http2: require.resolve('./empty-module.js'),
    net: require.resolve('./empty-module.js'),
    tls: require.resolve('./empty-module.js'),
    dgram: require.resolve('./empty-module.js'),
    dns: require.resolve('./empty-module.js'),
    util: require.resolve('util'),
    assert: require.resolve('assert'),
    assert: require.resolve('assert'),
    tty: require.resolve('./empty-module.js'),
    fs: require.resolve('./empty-module.js'),
};

module.exports = config;
// module.exports = withNativeWind(config, { input: './global.css' });
