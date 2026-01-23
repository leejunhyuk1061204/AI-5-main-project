const path = require('path');
try {
    const pluginPath = require.resolve('@react-native/gradle-plugin/package.json', { paths: [require.resolve('react-native/package.json')] });
    console.log('Resolved path:', pluginPath);
    console.log('Parent dir:', path.dirname(pluginPath));
} catch (e) {
    console.error('Error resolving:', e);
}
