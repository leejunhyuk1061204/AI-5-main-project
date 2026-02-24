const { withAppBuildGradle } = require('@expo/config-plugins');

/**
 * Expo SDK 54가 prebuild 시 자동으로 추가하는 enableBundleCompression 속성을 제거합니다.
 * 이 속성은 React Native 0.81+에서만 지원되며, RN 0.76.7에서는 존재하지 않아
 * "Could not set unknown property 'enableBundleCompression'" 에러가 발생합니다.
 */
const withRemoveBundleCompression = (config) => {
    return withAppBuildGradle(config, (config) => {
        const buildGradle = config.modResults.contents;

        // enableBundleCompression 라인 제거
        config.modResults.contents = buildGradle.replace(
            /\s*enableBundleCompression\s*=.*\n/g,
            '\n'
        );

        return config;
    });
};

module.exports = withRemoveBundleCompression;
