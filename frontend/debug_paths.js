const path = require('path');
const fs = require('fs');

try {
    const rnPackage = require.resolve('react-native/package.json');
    console.log('React Native package found at:', rnPackage);

    const rngpPackage = require.resolve('@react-native/gradle-plugin/package.json', { paths: [rnPackage] });
    console.log('React Native Gradle Plugin found at:', rngpPackage);

    console.log('Parent dir:', path.dirname(rngpPackage));

    const expoAutolinking = require.resolve('expo-modules-autolinking/package.json', { paths: [require.resolve('expo/package.json')] });
    console.log('Expo Autolinking found at:', expoAutolinking);

} catch (e) {
    console.error('Error resolving paths:', e);
}
