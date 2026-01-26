const { withProjectBuildGradle } = require('@expo/config-plugins');

const withNotifeeRepo = (config) => {
    return withProjectBuildGradle(config, (config) => {
        const buildGradle = config.modResults.contents;
        const notifeeRepo = `maven { url "$rootDir/../node_modules/@notifee/react-native/android/libs" }`;

        // 이미 추가되어 있는지 확인
        if (buildGradle.includes('notifee/react-native/android/libs')) {
            return config;
        }

        // allprojects { repositories { ... } } 안에 추가
        // 정규표현식으로 allprojects 블록 내부의 repositories 시작 부분을 찾아서 삽입
        config.modResults.contents = buildGradle.replace(
            /allprojects\s*{\s*repositories\s*{/,
            `allprojects {
  repositories {
    ${notifeeRepo}`
        );

        return config;
    });
};

module.exports = withNotifeeRepo;
